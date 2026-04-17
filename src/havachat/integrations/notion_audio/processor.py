"""
Audio Processor for Notion Audio Content Database

Processes Notion records marked "Ready for Audio" and generates high-quality
audio files with timestamps using ElevenLabs TTS.
"""

import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from loguru import logger

from src.havachat.utils.notion_client import NotionClient
from src.models.notion_audio import (
    AudioProcessorConfig,
    ProcessingResult,
    BatchProcessingSummary,
    AudioContentStatus
)
from src.havachat.integrations.notion_audio.utils import (
    get_audio_storage_path,
    should_regenerate_audio,
    save_content_hash,
    compute_content_hash
)
from src.tools.audio.tts_with_elevenlabs import text_to_speech_with_timestamps


class AudioProcessor:
    """
    Batch processor for Notion Audio Content Database.
    
    Queries records with Status = "Ready for Audio", generates audio files
    with timestamps, and updates Notion with completion status.
    """
    
    def __init__(
        self,
        notion_client: NotionClient,
        config: AudioProcessorConfig,
        voice_resolver: Optional[Any] = None,
        metadata_generator: Optional[Any] = None
    ):
        """
        Initialize AudioProcessor.
        
        Args:
            notion_client: Shared NotionClient instance
            config: Configuration with API keys and paths
            voice_resolver: Optional VoiceResolver for US3 (voice selection)
            metadata_generator: Optional MetadataGenerator for US2 (AI metadata)
        """
        self.notion_client = notion_client
        self.config = config
        self.voice_resolver = voice_resolver
        self.metadata_generator = metadata_generator
    
    def _extract_record_properties(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract properties from Notion page object.
        
        Args:
            page: Notion page object from query
        
        Returns:
            Dictionary with extracted properties
        """
        properties = page.get("properties", {})
        
        # Extract Idx (title property)
        idx_prop = properties.get("Idx", {})
        idx = page.get("id")
        if idx_prop.get("type") == "unique_id" and idx_prop.get("unique_id"):
            idx = f'{idx_prop["unique_id"].get("prefix", "")}-{idx_prop["unique_id"].get("number", "")}'

        # Extract Name (title property)
        name_prop = properties.get("Name", {})
        name = ""
        if name_prop.get("type") == "title" and name_prop.get("title"):
            name = "".join([t.get("plain_text", "") for t in name_prop["title"]])
        
        # Extract Content (rich_text property)
        content_prop = properties.get("Content", {})
        content = ""
        if content_prop.get("type") == "rich_text" and content_prop.get("rich_text"):
            content = "".join([t.get("plain_text", "") for t in content_prop["rich_text"]])
        
        # Extract Topic (select property)
        topic_prop = properties.get("Topic", {})
        topic = ""
        if topic_prop.get("type") == "select" and topic_prop.get("select"):
            topic = topic_prop["select"].get("name", "")
        
        # Extract Sub-Type (select property)
        subtype_prop = properties.get("Sub-Type", {})
        sub_type = ""
        if subtype_prop.get("type") == "select" and subtype_prop.get("select"):
            sub_type = subtype_prop["select"].get("name", "")
        
        # Extract Voices relation (for US3 - voice selection)
        voices_prop = properties.get("Voices", {})
        voices_relations = []
        if voices_prop.get("type") == "relation" and voices_prop.get("relation"):
            voices_relations = [r.get("id") for r in voices_prop["relation"]]
        
        return {
            "id": idx,
            "url": page.get("url"),
            "name": name,
            "content": content,
            "topic": topic,
            "sub_type": sub_type,
            "voices": voices_relations
        }
    
    def _generate_audio(
        self,
        content: str,
        voice_id: str,
        output_path: Path
    ) -> bool:
        """
        Generate audio file using ElevenLabs TTS with timestamps.
        
        REUSE existing tool with timestamps!
        
        Args:
            content: Text content to convert to speech
            voice_id: ElevenLabs voice ID
            output_path: Path where audio file will be saved
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Call existing text_to_speech_with_timestamps tool
            transcript, _ = text_to_speech_with_timestamps(
                text=content,
                voice_id=voice_id,
                output_path=str(output_path),
                save_transcript=True,
                output_format=self.config.audio_format,
                model_id=self.config.tts_model
            )
            
            logger.info(
                f"Generated audio: {output_path.name} "
                f"(duration: {transcript.segments[-1].end:.1f}s)"
            )
            return True
            
        except Exception as e:
            logger.error(f"Audio generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_record(self, record: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single audio content record.
        
        Workflow:
        1. Extract properties from Notion page
        2. Check duplicate detection (skip if unchanged)
        3. Resolve voice ID (default for US1, VoiceResolver for US3)
        4. Generate audio file with timestamps
        5. Generate metadata (US2 only)
        6. Update Notion with completion status
        
        Args:
            record: Notion page object
        
        Returns:
            ProcessingResult with success/failure details
        """
        start_time = time.time()
        
        try:
            # Extract properties
            props = self._extract_record_properties(record)
            record_id = props["id"]
            record_name = props["name"]
            
            logger.info(f"Processing: {record_name} (ID: {record_id})")
            
            # Validate required fields
            if not props["content"]:
                return ProcessingResult(
                    record_id=record_id,
                    record_name=record_name,
                    success=False,
                    error="Empty content field",
                    processing_time=time.time() - start_time
                )
            
            if not props["topic"] or not props["sub_type"]:
                return ProcessingResult(
                    record_id=record_id,
                    record_name=record_name,
                    success=False,
                    error="Missing topic or sub-type",
                    processing_time=time.time() - start_time
                )
            
            # Construct audio file path
            audio_path = get_audio_storage_path(
                base_path=self.config.storage_path,
                topic=props["topic"],
                sub_type=props["sub_type"],
                record_id=record_id,
                record_name=record_name
            )
            
            # Check duplicate detection
            if not should_regenerate_audio(audio_path, props["content"]):
                logger.info(f"Skipping {record_name} - content unchanged")
                return ProcessingResult(
                    record_id=record_id,
                    record_name=record_name,
                    success=True,
                    audio_path=audio_path,
                    processing_time=time.time() - start_time,
                    skipped=True
                )
            
            # Resolve voice ID
            # US1 (MVP): Use default voice
            # US3 (Voice Selection): Use VoiceResolver if available
            if self.voice_resolver and props["voices"]:
                voice_id = self.voice_resolver.resolve_voice(props["voices"][0])
            else:
                voice_id = self.config.default_voice_id
            
            logger.info(f"Using voice: {voice_id}")
            
            # Generate audio
            success = self._generate_audio(
                content=props["content"],
                voice_id=voice_id,
                output_path=audio_path
            )
            
            if not success:
                return ProcessingResult(
                    record_id=record_id,
                    record_name=record_name,
                    success=False,
                    error="Audio generation failed",
                    processing_time=time.time() - start_time
                )
            
            # Save content hash for duplicate detection
            content_hash = compute_content_hash(props["content"])
            save_content_hash(audio_path, content_hash)
            
            # Generate metadata (US2 only)
            if self.metadata_generator:
                try:
                    metadata = self.metadata_generator.generate_metadata(
                        content=props["content"],
                        topic=props["topic"],
                        sub_type=props["sub_type"]
                    )
                    
                    # Update Notion with metadata
                    self.notion_client.update_page_properties(
                        page_id=record_id,
                        properties={
                            "Description": {
                                "rich_text": [{"text": {"content": metadata.description}}]
                            },
                            "Tags": {
                                "rich_text": [{"text": {"content": metadata.tags_as_string()}}]
                            }
                        }
                    )
                    logger.info(f"Updated metadata for {record_name}")
                except Exception as e:
                    logger.warning(f"Metadata generation failed: {str(e)}")
                    # Continue - audio file is still valid
            
            # Update Notion status to Completed
            self.notion_client.update_page_properties(
                page_id=record.get('id', record_id),
                properties={
                    "Status": {"status": {"name": AudioContentStatus.AUDIO_COMPLETED.value}}
                }
            )
            
            logger.success(f"Completed: {record_name}")
            
            return ProcessingResult(
                record_id=record_id,
                record_name=record_name,
                success=True,
                audio_path=audio_path,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Processing failed for {record.get('id', 'unknown')}: {str(e)}")
            return ProcessingResult(
                record_id=record.get("id", "unknown"),
                record_name=props.get("name", "unknown") if 'props' in locals() else "unknown",
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def process_batch(
        self,
        limit: Optional[int] = None,
        record_id: Optional[str] = None
    ) -> BatchProcessingSummary:
        """
        Process batch of audio content records.
        
        Queries Notion Audio Database for records with Status = "Ready for Audio"
        and processes them sequentially with per-record error isolation.
        
        Args:
            limit: Optional limit on number of records to process
            record_id: Optional specific record ID to process
        
        Returns:
            BatchProcessingSummary with aggregate results
        """
        batch_start_time = time.time()
        
        logger.info("Starting batch processing")
        
        # Query Notion Audio Database
        if record_id:
            # Process specific record (for testing/debugging)
            logger.info(f"Processing single record: {record_id}")
            filters = {
                "property": "id",
                "rich_text": {"equals": record_id}
            }
        else:
            # Query for "Ready for Audio" status
            filters = {
                "property": "Status",
                "status": {"equals": AudioContentStatus.READY_FOR_AUDIO.value}
            }
        
        try:
            records = self.notion_client.query_database_filtered(
                database_id=self.config.notion_audio_db_id,
                filters=filters,
                page_size=limit if limit else 100
            )
            
            if limit and len(records) > limit:
                records = records[:limit]
            
            logger.info(f"Found {len(records)} records to process")
            
        except Exception as e:
            logger.error(f"Failed to query Notion database: {str(e)}")
            return BatchProcessingSummary(
                total_records=0,
                successful=0,
                failed=1,
                skipped=0,
                total_time=time.time() - batch_start_time,
                results=[]
            )
        
        # Process records sequentially
        results: List[ProcessingResult] = []
        for i, record in enumerate(records, 1):
            logger.info(f"Progress: {i}/{len(records)}")
            result = self._process_record(record)
            results.append(result)
        
        # Calculate summary
        successful = sum(1 for r in results if r.success and not r.skipped)
        failed = sum(1 for r in results if not r.success)
        skipped = sum(1 for r in results if r.skipped)
        
        summary = BatchProcessingSummary(
            total_records=len(records),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_time=time.time() - batch_start_time,
            results=results
        )
        
        logger.info(
            f"Batch complete: {successful} successful, {failed} failed, "
            f"{skipped} skipped, {summary.success_rate:.1f}% success rate"
        )
        
        return summary
