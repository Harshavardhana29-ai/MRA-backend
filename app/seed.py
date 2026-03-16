"""
Seed script for MRA database.
Run: python -m app.seed
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Agent, AgentTopicMapping


# ── Agent definitions ────────────────────────────────────────────
AGENTS = [
    {
        "name": "News Aggregator",
        "description": "Enterprise News AI Agent — aggregates and summarizes news from multiple sources",
        "api_url": "https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask",
        "api_method": "POST",
    },
    {
        "name": "Sentiment Analyzer",
        "description": "Analyzes sentiment across articles and data sources",
        "api_url": None,
        "api_method": "POST",
    },
    {
        "name": "Trend Detector",
        "description": "Detects emerging trends and patterns from data",
        "api_url": None,
        "api_method": "POST",
    },
    {
        "name": "Data Extractor",
        "description": "Extracts structured data from unstructured sources",
        "api_url": None,
        "api_method": "POST",
    },
    {
        "name": "Report Generator",
        "description": "Generates comprehensive analysis reports",
        "api_url": None,
        "api_method": "POST",
    },
]

# ── Topic → Agent mappings ───────────────────────────────────────
TOPIC_AGENT_MAP = {
    "AI": ["News Aggregator", "Sentiment Analyzer", "Trend Detector"],
    "Technology": ["News Aggregator", "Data Extractor", "Report Generator"],
    "Finance": ["Trend Detector", "Report Generator", "Data Extractor"],
    "Sports": ["Data Extractor", "Sentiment Analyzer"],
    "General": ["News Aggregator", "Report Generator"],
    "Healthcare": ["News Aggregator", "Data Extractor"],
    "Energy": ["Trend Detector", "Report Generator"],
    "Automotive": ["News Aggregator", "Trend Detector", "Report Generator"],
}


async def seed():
    async with AsyncSessionLocal() as db:
        print("🌱 Seeding agents...")

        agent_map: dict[str, Agent] = {}

        for agent_data in AGENTS:
            # Check if agent already exists
            result = await db.execute(
                select(Agent).where(Agent.name == agent_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ✓ Agent '{agent_data['name']}' already exists — skipping")
                agent_map[agent_data["name"]] = existing
            else:
                agent = Agent(
                    name=agent_data["name"],
                    description=agent_data["description"],
                    api_url=agent_data["api_url"],
                    api_method=agent_data["api_method"],
                    is_active="true",
                )
                db.add(agent)
                await db.flush()
                agent_map[agent_data["name"]] = agent
                print(f"  + Created agent '{agent_data['name']}'" +
                      (f" → {agent_data['api_url']}" if agent_data["api_url"] else ""))

        print("\n🔗 Seeding topic → agent mappings...")

        for topic, agent_names in TOPIC_AGENT_MAP.items():
            for agent_name in agent_names:
                agent = agent_map.get(agent_name)
                if not agent:
                    print(f"  ✗ Agent '{agent_name}' not found — skipping mapping to '{topic}'")
                    continue

                # Check if mapping already exists
                result = await db.execute(
                    select(AgentTopicMapping).where(
                        AgentTopicMapping.agent_id == agent.id,
                        AgentTopicMapping.topic == topic,
                    )
                )
                existing_mapping = result.scalar_one_or_none()

                if existing_mapping:
                    print(f"  ✓ {topic} → {agent_name} already exists — skipping")
                else:
                    mapping = AgentTopicMapping(
                        agent_id=agent.id,
                        topic=topic,
                    )
                    db.add(mapping)
                    print(f"  + {topic} → {agent_name}")

        await db.commit()
        print("\n✅ Seed completed successfully!")

        # Print summary
        agent_count = (await db.execute(select(Agent))).scalars().all()
        mapping_count = (await db.execute(select(AgentTopicMapping))).scalars().all()
        print(f"\n📊 Summary: {len(agent_count)} agents, {len(mapping_count)} topic mappings")


if __name__ == "__main__":
    asyncio.run(seed())
