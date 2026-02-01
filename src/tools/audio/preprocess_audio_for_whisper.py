import os.path
import subprocess
import tempfile

downsample_audio_command = (
    "ffmpeg -i '{input_file}' -ar {sample_rate} "
    "-ac 1 -map 0:a: '{output_file}'"
)


def downsample_audio(
    input_file: str, output_file: str = None, sample_rate: int = 16000
) -> str:
    """
    Downsample audio to 16kHz mono
    """
    # get input file name

    output_file = output_file or tempfile.mktemp(os.path.basename(input_file))

    command = downsample_audio_command.format(
        input_file=input_file, sample_rate=sample_rate, output_file=output_file
    )

    subprocess.run(command, shell=True, check=True)

    return output_file


if __name__ == "__main__":
    import sys

    output_file = (
        sys.argv[2]
        if len(sys.argv) > 2
        else f"{sys.argv[1].rsplit('.', 1)[0]}_out"
        f".{sys.argv[1].rsplit('.', 1)[-1]}"
    )

    downsample_audio(
        sys.argv[1],
        output_file=output_file,
    )
