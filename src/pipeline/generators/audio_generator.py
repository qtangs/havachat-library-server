"""Audio generator for learning items and content units using ElevenLabs TTS."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Literal
from uuid import uuid4

from src.pipeline.models.audio_metadata import (
    AudioVersion,
    ContentUnitAudio,
    LearningItemAudio,
    SegmentAudio,
)
from src.pipeline.models.audio_progress import (
    AudioGenerationProgress,
    AudioProgressItem,
)
from src.pipeline.utils.elevenlabs_client import ElevenLabsClient
from src.pipeline.validators.schema import ContentUnit, LearningItem
from src.pipeline.validators.voice_validator import VoiceConfigValidator

logger = logging.getLogger(__name__)


class AudioGenerator:
    """Generator for audio files using ElevenLabs TTS."""
    
    def __init__(
        self,
        elevenlabs_client: ElevenLabsClient,
        voice_validator: VoiceConfigValidator,
        output_base_path: str | Path,
        knowledge_base_path: str | Path
    ):
        """Initialize audio generator.
        
        Args:
            elevenlabs_client: ElevenLabs TTS client
            voice_validator: Voice configuration validator
            output_base_path: Base path for audio output (e.g., /path/to/havachat-knowledge/generated content/)
            knowledge_base_path: Base path to knowledge repository
        """
        self.elevenlabs = elevenlabs_client
        self.voice_validator = voice_validator
        self.output_base_path = Path(output_base_path)
        self.knowledge_base_path = Path(knowledge_base_path)
    
    def load_learning_items(
        self,
        language: str,
        level: str,
        category: str | None = None
    ) -> List[LearningItem]:
        """Load learning items from consolidated JSON files.
        
        Args:
            language: Full language name (e.g., "Mandarin", "French", "Japanese")
            level: Level (e.g., "HSK1", "A1", "N5")
            category: Optional category filter (vocab, grammar, idiom, etc.)
            
        Returns:
            List of LearningItem objects
        """
        base_path = self.knowledge_base_path / language / level / "02_Generated"
        
        items = []
        
        if category:
            # Load specific category file
            file_path = base_path / f"{category}_enriched.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    items.extend([LearningItem(**item) for item in data])
                    logger.info(f"Loaded {len(data)} items from {file_path}")
        else:
            # Load all category files
            for cat_file in base_path.glob("*_enriched.json"):
                with open(cat_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    items.extend([LearningItem(**item) for item in data])
                    logger.info(f"Loaded {len(data)} items from {cat_file}")
        
        logger.info(f"Total learning items loaded: {len(items)}")
        return items
    
    def load_content_units(
        self,
        language: str,
        level: str,
        content_type: Literal["conversation", "story"] | None = None
    ) -> List[ContentUnit]:
        """Load content units from JSON files.
        
        Args:
            language: Full language name
            level: Level
            content_type: Optional type filter (conversation or story)
            
        Returns:
            List of ContentUnit objects
        """
        base_path = self.knowledge_base_path / language / level / "02_Generated"
        
        units = []
        
        types_to_load = [content_type] if content_type else ["conversation", "story"]
        
        for ctype in types_to_load:
            type_dir = base_path / ctype
            if not type_dir.exists():
                logger.warning(f"Directory not found: {type_dir}")
                continue
            
            for content_file in type_dir.glob(f"{ctype}_*.json"):
                try:
                    with open(content_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        unit = ContentUnit(**data)
                        units.append(unit)
                except Exception as e:
                    logger.error(f"Error loading {content_file}: {e}")
        
        logger.info(f"Total content units loaded: {len(units)}")
        return units
    
    def generate_audio_for_item(
        self,
        item: LearningItem,
        voice_id: str,
        language_full: str,
        level: str,
        versions: int = 1,
        audio_format: Literal["opus", "mp3"] = "opus"
    ) -> LearningItemAudio | None:
        """Generate audio for a learning item.
        
        Args:
            item: LearningItem to generate audio for
            voice_id: ElevenLabs voice ID
            language_full: Full language name (Mandarin, French, Japanese)
            level: Level (HSK1, A1, N5)
            versions: Number of versions to generate (1-3)
            audio_format: Audio format (opus or mp3)
            
        Returns:
            LearningItemAudio object or None if failed
        """
        # Validate voice configuration (validator already has language_code)
        is_valid, error = self.voice_validator.validate_voice_config(voice_id)
        if not is_valid:
            logger.error(f"Voice validation failed: {error}")
            return None
        
        # Prepare output directory
        audio_dir = (
            self.output_base_path / language_full / level / "02_Generated" / 
            "audio" / item.category.value
        )
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        item_audio = LearningItemAudio(
            learning_item_id=item.id,
            target_item=item.target_item,
            category=item.category.value,
            versions=[]
        )
        
        # Generate requested number of versions
        for version_num in range(1, versions + 1):
            # Create filename with version suffix
            filename = f"{item.id}_v{version_num}.{audio_format}"
            output_path = audio_dir / filename
            
            # Generate audio
            success, metadata = self.elevenlabs.text_to_speech(
                text=item.target_item,
                voice_id=voice_id,
                output_path=output_path,
                audio_format=audio_format
            )
            
            if success:
                # Create audio version metadata
                audio_version = AudioVersion(
                    version=version_num,
                    audio_local_path=f"audio/{item.category.value}/{filename}",
                    audio_url=None,  # Will be set after R2 sync
                    format=audio_format,
                    sample_rate=metadata["sample_rate"],
                    bitrate=metadata["bitrate"],
                    file_size_bytes=metadata.get("file_size_bytes"),
                    duration_ms=metadata.get("duration_ms"),
                    voice_id=voice_id,
                    character_count=metadata["character_count"],
                    selected=(version_num == 1)  # First version selected by default
                )
                
                item_audio.versions.append(audio_version)
                logger.info(
                    f"✓ Generated audio v{version_num} for item: {item.target_item} "
                    f"({metadata['character_count']} chars)"
                )
            else:
                logger.error(
                    f"✗ Failed to generate audio v{version_num} for item: {item.target_item}"
                )
        
        return item_audio if item_audio.versions else None
    
    def generate_audio_for_content(
        self,
        content_unit: ContentUnit,
        voice_mapping: dict[str, str],  # speaker_id -> voice_id
        language_full: str,
        level: str,
        versions: int = 1,
        audio_format: Literal["opus", "mp3"] = "opus"
    ) -> ContentUnitAudio | None:
        """Generate audio for content unit with speaker-aware voice mapping.
        
        Args:
            content_unit: ContentUnit to generate audio for
            voice_mapping: Dict mapping speaker IDs to voice IDs
            language_full: Full language name
            level: Level
            versions: Number of versions to generate (1-3)
            audio_format: Audio format
            
        Returns:
            ContentUnitAudio object or None if failed
        """
        # Validate all voices in mapping (validator already has language_code)
        for speaker_id, voice_id in voice_mapping.items():
            is_valid, error = self.voice_validator.validate_voice_config(voice_id)
            if not is_valid:
                logger.error(f"Voice validation failed for speaker {speaker_id}: {error}")
                return None
        
        # Prepare output directory
        audio_dir = (
            self.output_base_path / language_full / level / "02_Generated" / 
            "audio" / content_unit.type.value
        )
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        content_audio = ContentUnitAudio(
            content_unit_id=content_unit.id,
            title=content_unit.title,
            type=content_unit.type.value,
            segments=[]
        )
        
        # Generate audio for each segment
        for seg_idx, segment in enumerate(content_unit.segments):
            # Get voice ID for this segment's speaker
            voice_id = voice_mapping.get(segment.speaker, list(voice_mapping.values())[0])
            
            segment_audio = SegmentAudio(
                segment_index=seg_idx,
                speaker_id=segment.speaker,
                text=segment.text,
                versions=[]
            )
            
            # Generate requested versions
            for version_num in range(1, versions + 1):
                filename = f"{content_unit.id}_seg{seg_idx}_v{version_num}.{audio_format}"
                output_path = audio_dir / filename
                
                success, metadata = self.elevenlabs.text_to_speech(
                    text=segment.text,
                    voice_id=voice_id,
                    output_path=output_path,
                    audio_format=audio_format
                )
                
                if success:
                    audio_version = AudioVersion(
                        version=version_num,
                        audio_local_path=f"audio/{content_unit.type.value}/{filename}",
                        audio_url=None,
                        format=audio_format,
                        sample_rate=metadata["sample_rate"],
                        bitrate=metadata["bitrate"],
                        file_size_bytes=metadata.get("file_size_bytes"),
                        duration_ms=metadata.get("duration_ms"),
                        voice_id=voice_id,
                        character_count=metadata["character_count"],
                        selected=(version_num == 1)
                    )
                    
                    segment_audio.versions.append(audio_version)
                    logger.info(
                        f"✓ Generated audio v{version_num} for segment {seg_idx}: "
                        f"{segment.text[:50]}... ({metadata['character_count']} chars)"
                    )
                else:
                    logger.error(
                        f"✗ Failed to generate audio v{version_num} for segment {seg_idx}"
                    )
            
            if segment_audio.versions:
                content_audio.segments.append(segment_audio)
        
        return content_audio if content_audio.segments else None
    
    def generate_audio_for_content_dialogue(
        self,
        content_unit: ContentUnit,
        voice_mapping: dict[str, str],  # speaker_id -> voice_id
        language_full: str,
        level: str,
        versions: int = 1,
        audio_format: Literal["opus", "mp3"] = "opus"
    ) -> ContentUnitAudio | None:
        """Generate audio for entire conversation using Text-to-Dialogue API.
        
        This method generates a single audio file per version containing the entire
        dialogue, making it more natural-sounding than individual segments.
        
        Args:
            content_unit: ContentUnit to generate audio for
            voice_mapping: Dict mapping speaker IDs to voice IDs
            language_full: Full language name
            level: Level
            versions: Number of versions to generate (1-3)
            audio_format: Audio format
            
        Returns:
            ContentUnitAudio object or None if failed
        """
        # Validate all voices in mapping
        for speaker_id, voice_id in voice_mapping.items():
            is_valid, error = self.voice_validator.validate_voice_config(voice_id)
            if not is_valid:
                logger.error(f"Voice validation failed for speaker {speaker_id}: {error}")
                return None
        
        # Prepare output directory
        audio_dir = (
            self.output_base_path / language_full / level / "02_Generated" / 
            "audio" / content_unit.type.value
        )
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Build dialogue inputs for the API
        dialogue_inputs = []
        for segment in content_unit.segments:
            voice_id = voice_mapping.get(segment.speaker, list(voice_mapping.values())[0])
            dialogue_inputs.append({
                "text": segment.text,
                "voice_id": voice_id
            })
        
        content_audio = ContentUnitAudio(
            content_unit_id=content_unit.id,
            title=content_unit.title,
            type=content_unit.type.value,
            segments=[]
        )
        
        # Generate requested versions
        for version_num in range(1, versions + 1):
            filename = f"{content_unit.id}_dialogue_v{version_num}.{audio_format}"
            output_path = audio_dir / filename
            
            success, metadata = self.elevenlabs.text_to_dialogue(
                dialogue_inputs=dialogue_inputs,
                output_path=output_path,
                audio_format=audio_format
            )
            
            if success:
                # Save metadata JSON alongside audio file
                metadata_filename = f"{content_unit.id}_dialogue_v{version_num}_metadata.json"
                metadata_path = audio_dir / metadata_filename
                
                audio_metadata_info = {
                    "content_unit_id": content_unit.id,
                    "title": content_unit.title,
                    "type": content_unit.type.value,
                    "version": version_num,
                    "audio_file": filename,
                    "format": audio_format,
                    "sample_rate": metadata["sample_rate"],
                    "bitrate": metadata["bitrate"],
                    "file_size_bytes": metadata.get("file_size_bytes"),
                    "duration_ms": metadata.get("duration_ms"),
                    "character_count": metadata["character_count"],
                    "num_segments": len(dialogue_inputs),
                    "voice_mapping": voice_mapping,
                    "dialogue_inputs": dialogue_inputs,
                    "generated_at": datetime.now(UTC).isoformat()
                }
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(audio_metadata_info, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved audio metadata to {metadata_path}")
                
                # Create a single "full dialogue" segment with the complete audio
                segment_audio = SegmentAudio(
                    segment_index=0,
                    speaker_id="ALL",
                    text=content_unit.text,  # Full dialogue text
                    versions=[]
                )
                
                audio_version = AudioVersion(
                    version=version_num,
                    audio_local_path=f"audio/{content_unit.type.value}/{filename}",
                    audio_url=None,
                    format=audio_format,
                    sample_rate=metadata["sample_rate"],
                    bitrate=metadata["bitrate"],
                    file_size_bytes=metadata.get("file_size_bytes"),
                    duration_ms=metadata.get("duration_ms"),
                    voice_id="multiple",  # Multiple speakers
                    character_count=metadata["character_count"],
                    selected=(version_num == 1)
                )
                
                segment_audio.versions.append(audio_version)
                content_audio.segments.append(segment_audio)
                
                logger.info(
                    f"✓ Generated dialogue v{version_num}: "
                    f"{len(dialogue_inputs)} segments, {metadata['character_count']} chars total"
                )
            else:
                logger.error(
                    f"✗ Failed to generate dialogue v{version_num}"
                )
        
        return content_audio if content_audio.segments else None
    
    def save_metadata(
        self,
        metadata_list: List[LearningItemAudio | ContentUnitAudio],
        language_full: str,
        level: str,
        item_type: Literal["learning_items", "content_units"]
    ):
        """Save audio metadata to JSON file.
        
        Args:
            metadata_list: List of audio metadata objects
            language_full: Full language name
            level: Level
            item_type: Type of items (learning_items or content_units)
        """
        output_dir = self.output_base_path / language_full / level / "02_Generated" / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{item_type}_media.json"
        
        # Convert to dict for JSON serialization
        data = [item.model_dump(mode='json') for item in metadata_list]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(metadata_list)} audio metadata entries to {output_file}")
    
    def load_metadata(
        self,
        language_full: str,
        level: str,
        item_type: Literal["learning_items", "content_units"]
    ) -> List[LearningItemAudio | ContentUnitAudio]:
        """Load audio metadata from JSON file.
        
        Args:
            language_full: Full language name
            level: Level
            item_type: Type of items
            
        Returns:
            List of audio metadata objects
        """
        output_file = (
            self.output_base_path / language_full / level / "02_Generated" / 
            "audio" / f"{item_type}_media.json"
        )
        
        if not output_file.exists():
            logger.warning(f"Metadata file not found: {output_file}")
            return []
        
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to appropriate model
        if item_type == "learning_items":
            return [LearningItemAudio(**item) for item in data]
        else:
            return [ContentUnitAudio(**item) for item in data]
