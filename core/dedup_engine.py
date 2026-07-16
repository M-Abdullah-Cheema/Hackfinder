import logging
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import FinalOpportunity

logger = logging.getLogger(__name__)

class DeduplicationEngine:
    def __init__(self):
        # 0.08 distance threshold acts as a strict 92% similarity barrier
        self.similarity_threshold = 0.08 

    async def evaluate_incoming_record(self, record_data: dict, vector: list[float]) -> bool:
        """
        Executes a two-tier safety validation pass. 
        Returns True if a conflict is detected and resolved, False if entirely unique.
        """
        async with AsyncSessionLocal() as session:
            
            # ==========================================
            # TIER A: Deterministic Exact Match Passes
            # ==========================================
            query = select(FinalOpportunity).where(
                (FinalOpportunity.platform_post_id == record_data["platform_post_id"]) |
                (FinalOpportunity.registration_url == record_data.get("registration_url", "NO_URL"))
            )
            result = await session.execute(query)
            exact_match = result.scalars().first()
            
            if exact_match:
                logger.info(f"🔄 Exact duplicate found via Tier A constraints for: {record_data['title']}")
                await self._merge_records(session, exact_match, record_data)
                return True

            # ==========================================
            # TIER B: Localized Vector Database Match Passes
            # ==========================================
            # Native pgvector cosine distance calculation performed directly inside Postgres
            query = select(FinalOpportunity).filter(
                FinalOpportunity.embedding.cosine_distance(vector) < self.similarity_threshold
            ).order_by(
                FinalOpportunity.embedding.cosine_distance(vector)
            ).limit(1)
            
            result = await session.execute(query)
            semantic_match = result.scalars().first()

            if semantic_match:
                logger.warning(f"🧠 Semantic collision detected via Tier B graph index. Merging into: {semantic_match.title}")
                await self._merge_records(session, semantic_match, record_data)
                return True
                
            return False

    async def _merge_records(self, session, existing_record: FinalOpportunity, incoming_data: dict):
        """Amalgamates unique structural values from the duplicate asset into the parent entity."""
        state_modified = False
        
        if incoming_data.get("registration_url") and not existing_record.registration_url:
            existing_record.registration_url = incoming_data["registration_url"]
            state_modified = True
            
        if state_modified:
            await session.commit()
            logger.info(f"✨ Parent record updated with missing relational properties successfully.")