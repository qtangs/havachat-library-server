from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from models.video_production import (
    VideoCompositionConfig,
    VideoCompositionError,
    VideoFormat,
    VideoProductionResult,
    VideoResolution,
)


class KaraokeRenderer:
    """Converts ElevenLabs word-level transcripts to ASS karaoke subtitle files."""

    ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    @staticmethod
    def _ts(seconds: float) -> str:
        """Format seconds as ASS timestamp H:MM:SS.cc"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    @classmethod
    def render(
        cls,
        transcript,  # Transcript instance (pydantic v1)
        output_path: Path,
        resolution: "VideoResolution",
        font_size: int = 48,
    ) -> None:
        """Write an ASS file with \\k karaoke tags to output_path."""
        lines: list[str] = []
        lines.append(cls.ASS_HEADER.format(
            width=resolution.width,
            height=resolution.height,
            fontsize=font_size,
        ))

        for segment in transcript.segments:
            words = segment.words or []
            if not words:
                continue

            seg_start = segment.start
            seg_end = segment.end

            # Build karaoke text: {\\kN}word for each word
            # N is duration in centiseconds
            karaoke_parts: list[str] = []
            for w in words:
                w_start = w.start if w.start is not None else seg_start
                w_end = w.end if w.end is not None else seg_end
                duration_cs = max(1, int((w_end - w_start) * 100))
                karaoke_parts.append(f"{{\\k{duration_cs}}}{w.word}")

            karaoke_text = " ".join(karaoke_parts)
            line = f"Dialogue: 0,{cls._ts(seg_start)},{cls._ts(seg_end)},Default,,0,0,0,,{karaoke_text}"
            lines.append(line)

        output_path.write_text("\n".join(lines), encoding="utf-8")


class VideoComposer:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        if not shutil.which(ffmpeg_path):
            raise RuntimeError(
                f"ffmpeg not found on PATH (looked for: {ffmpeg_path!r}). "
                "Install ffmpeg and ensure it is on your system PATH."
            )
        self._ffmpeg_path = ffmpeg_path

    def _measure_audio_duration(self, path: Path) -> float:
        """Return audio duration in seconds using ffprobe."""
        import ffmpeg
        probe = ffmpeg.probe(str(path))
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream["duration"])
        return float(probe["format"]["duration"])

    def _generate_silence(self, duration_seconds: int, output_path: Path) -> None:
        """Generate a silent MP3 file of the given duration using ffmpeg."""
        cmd = [
            self._ffmpeg_path, "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_seconds),
            "-q:a", "9",  # smallest/fastest VBR MP3
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise VideoCompositionError(f"Failed to generate silence: {result.stderr}")

    def _stitch_audio_segments(
        self,
        segments: list[tuple[Path, Optional[int]]],
        output_path: Path,
    ) -> None:
        """Stitch audio segments + silence into a single audio file."""
        concat_parts: list[Path] = []
        tmp_dir = output_path.parent / "_tmp_stitch"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        for idx, (seg_path, pause_s) in enumerate(segments):
            concat_parts.append(seg_path)
            if pause_s and pause_s > 0:
                silence_path = tmp_dir / f"silence_{idx}.mp3"
                self._generate_silence(pause_s, silence_path)
                concat_parts.append(silence_path)

        # Write concat list file
        list_file = tmp_dir / "concat.txt"
        with list_file.open("w") as f:
            for p in concat_parts:
                f.write(f"file '{p.resolve()}'\n")

        cmd = [
            self._ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-q:a", "2",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise VideoCompositionError(f"Audio stitching failed: {result.stderr}")

    def _build_ffmpeg_pipeline(
        self,
        config: VideoCompositionConfig,
        final_audio_path: Path,
        ass_path: Optional[Path],
        resolution: VideoResolution,
    ):
        """Build ffmpeg-python filter graph and return output stream."""
        import ffmpeg

        audio_duration = self._measure_audio_duration(final_audio_path)

        # Loop background image for audio duration
        video = (
            ffmpeg
            .input(str(config.image_path), loop=1, t=audio_duration)
            .video
            .filter("scale", resolution.width, resolution.height)
        )

        # Fade in / out
        video = video.filter(
            "fade", type="in", start_time=0, duration=config.fade_in_seconds
        ).filter(
            "fade", type="out", start_time=audio_duration - config.fade_out_seconds,
            duration=config.fade_out_seconds
        )

        # ASS karaoke subtitles
        if ass_path and (config.enable_karaoke or config.video_format == VideoFormat.SHORTS):
            video = video.filter("ass", filename=str(ass_path))

        # Title card
        if config.title_card_text:
            video = video.drawtext(
                text=config.title_card_text,
                fontsize=config.title_card_font_size,
                fontcolor=config.title_card_color,
                x="(w-text_w)/2",
                y="h*0.2",
                enable=f"lte(t,{config.title_card_duration_seconds})",
            )

        audio = ffmpeg.input(str(final_audio_path)).audio

        return ffmpeg.output(
            video, audio,
            str(config.output_path),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
        ).overwrite_output()

    async def compose(self, config: VideoCompositionConfig) -> VideoProductionResult:
        """Compose audio + background image into a video."""
        t_start = time.monotonic()
        resolution = VideoResolution.from_format(config.video_format)

        # 1. Stitch audio segments if provided, otherwise use audio_path directly
        if config.script_segments:
            stitched_path = config.audio_path.parent / "_stitched.mp3"
            self._stitch_audio_segments(config.script_segments, stitched_path)
            final_audio_path = stitched_path
        else:
            final_audio_path = config.audio_path

        # 2. Shorts guard
        if config.video_format == VideoFormat.SHORTS:
            duration = self._measure_audio_duration(final_audio_path)
            if duration > 60:
                raise VideoCompositionError(
                    f"Shorts audio duration {duration:.1f}s exceeds 60-second limit"
                )

        # 3. Karaoke guard
        needs_karaoke = config.enable_karaoke or config.video_format == VideoFormat.SHORTS
        if needs_karaoke and config.transcript is None:
            raise VideoCompositionError(
                "transcript required for karaoke but none was provided"
            )

        # 4. Render ASS subtitles
        ass_path: Optional[Path] = None
        if needs_karaoke and config.transcript is not None:
            ass_path = config.output_path.parent / "_karaoke.ass"
            KaraokeRenderer.render(config.transcript, ass_path, resolution)

        # 5. Build + run FFmpeg pipeline
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        pipeline = self._build_ffmpeg_pipeline(config, final_audio_path, ass_path, resolution)

        try:
            pipeline.run(cmd=self._ffmpeg_path, quiet=True)
        except Exception as exc:
            raise VideoCompositionError(f"FFmpeg composition failed: {exc}") from exc

        # 6. Collect result
        t_end = time.monotonic()
        output_duration = self._measure_audio_duration(config.output_path)
        file_size = config.output_path.stat().st_size

        return VideoProductionResult(
            output_path=config.output_path,
            duration_seconds=output_duration,
            file_size_bytes=file_size,
            video_format=config.video_format,
            resolution=resolution,
            processing_time_seconds=t_end - t_start,
        )
