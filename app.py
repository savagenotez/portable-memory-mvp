from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portable_memory.db")
ENGINE_KWARGS: Dict[str, Any] = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    ENGINE_KWARGS["connect_args"] = {"check_same_thread": False}

app = FastAPI(title="Portable Memory MVP", version="0.1.0")
Base = declarative_base()
engine = create_engine(DATABASE_URL, **ENGINE_KWARGS)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def json_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def is_newer(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return left["updated_at"] >= right["updated_at"]


def newer_of(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return left if is_newer(left, right) else right


def merge_provenance(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    newer = left if left["captured_at"] >= right["captured_at"] else right
    merged = dict(newer)
    merged["confidence"] = max(left.get("confidence", 0), right.get("confidence", 0))
    return merged


def fact_key(item: Dict[str, Any]) -> str:
    return normalize_text(item["key"])


def preference_key(item: Dict[str, Any]) -> str:
    return normalize_text(item["key"])


def project_key(item: Dict[str, Any]) -> str:
    return normalize_text(item["name"])


def conversation_key(item: Dict[str, Any]) -> str:
    return str(item["conversation_id"])


def index_by_key(items: List[Dict[str, Any]], key_fn) -> Dict[str, Dict[str, Any]]:
    return {key_fn(item): item for item in items}


def unique_ids(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def make_conflict(state_type: str, object_key: str, field: str, left_value: Any, right_value: Any) -> Dict[str, Any]:
    return {
        "conflict_id": uuid_str(),
        "state_type": state_type,
        "object_key": object_key,
        "field": field,
        "left_value": left_value,
        "right_value": right_value,
        "status": "open",
        "detected_at": now_iso(),
    }


def package_checksum(pkg: Dict[str, Any]) -> str:
    text = json.dumps(pkg, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------
# SQLAlchemy models
# -------------------------------------------------------------------


class PackageORM(Base):
    __tablename__ = "packages"

    package_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    schema_version = Column(String, nullable=False, default="0.1.0")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    checksum = Column(String, nullable=False)
    raw_package = Column(JSON, nullable=False)

    facts = relationship("FactORM", back_populates="package", cascade="all, delete-orphan")
    preferences = relationship("PreferenceORM", back_populates="package", cascade="all, delete-orphan")
    projects = relationship("ProjectORM", back_populates="package", cascade="all, delete-orphan")
    conversation_summaries = relationship(
        "ConversationSummaryORM", back_populates="package", cascade="all, delete-orphan"
    )
    conflicts = relationship("ConflictORM", back_populates="package", cascade="all, delete-orphan")
    chunks = relationship("RetrievalChunkORM", back_populates="package", cascade="all, delete-orphan")


class PackageLineageORM(Base):
    __tablename__ = "package_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    ancestor_package_id = Column(String, nullable=False)
    relation_type = Column(String, nullable=False)  # parent / merge_ancestor


class FactORM(Base):
    __tablename__ = "facts"

    fact_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    fact_key = Column(String, nullable=False, index=True)
    fact_value = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    provenance = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True, index=True)

    package = relationship("PackageORM", back_populates="facts")


class PreferenceORM(Base):
    __tablename__ = "preferences"

    preference_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    preference_key = Column(String, nullable=False, index=True)
    preference_value = Column(JSON, nullable=False)
    strength = Column(String, nullable=False)
    provenance = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True, index=True)

    package = relationship("PackageORM", back_populates="preferences")


class ProjectORM(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    provenance = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True, index=True)

    package = relationship("PackageORM", back_populates="projects")


class ConversationSummaryORM(Base):
    __tablename__ = "conversation_summaries"

    conversation_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    provenance = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True, index=True)

    package = relationship("PackageORM", back_populates="conversation_summaries")


class ConflictORM(Base):
    __tablename__ = "conflicts"

    conflict_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    state_type = Column(String, nullable=False)
    object_key = Column(String, nullable=False)
    field = Column(String, nullable=False)
    left_value = Column(JSON, nullable=False)
    right_value = Column(JSON, nullable=False)
    status = Column(String, nullable=False, index=True)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(JSON, nullable=True)

    package = relationship("PackageORM", back_populates="conflicts")


class RetrievalChunkORM(Base):
    __tablename__ = "retrieval_chunks"

    chunk_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.package_id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String, nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)
    text_content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, default={})
    updated_at = Column(DateTime(timezone=True), nullable=False)

    package = relationship("PackageORM", back_populates="chunks")


# -------------------------------------------------------------------
# Pydantic models
# -------------------------------------------------------------------


class Provenance(BaseModel):
    source_type: str
    source_id: str
    message_id: Optional[str] = None
    captured_at: str
    confidence: float


class Fact(BaseModel):
    fact_id: str
    key: str
    value: Any
    status: str
    updated_at: str
    provenance: Provenance


class Preference(BaseModel):
    preference_id: str
    key: str
    value: Any
    strength: str
    updated_at: str
    provenance: Provenance


class Project(BaseModel):
    project_id: str
    name: str
    summary: str
    status: str
    updated_at: str
    provenance: Provenance


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    summary: str
    updated_at: str
    provenance: Provenance


class Conflict(BaseModel):
    conflict_id: str
    state_type: str
    object_key: str
    field: str
    left_value: Any
    right_value: Any
    status: str
    detected_at: str


class Lineage(BaseModel):
    parent_package_ids: List[str] = Field(default_factory=list)
    merge_ancestor_ids: List[str] = Field(default_factory=list)


class PackageState(BaseModel):
    facts: List[Fact] = Field(default_factory=list)
    preferences: List[Preference] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    conversation_summaries: List[ConversationSummary] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)


class MemoryPackage(BaseModel):
    schema_version: str = "0.1.0"
    package_id: str
    agent_id: str
    created_at: str
    updated_at: str
    lineage: Lineage
    state: PackageState


class MergeRequest(BaseModel):
    left_package_id: str
    right_package_id: str
    base_package_id: Optional[str] = None


class TranscriptMessage(BaseModel):
    role: str
    content: str
    message_id: Optional[str] = None
    created_at: Optional[str] = None


class IngestTranscriptRequest(BaseModel):
    agent_id: str
    conversation_id: str
    title: str
    messages: List[TranscriptMessage]


class RetrieveRequest(BaseModel):
    agent_id: str
    query: str
    top_k: int = 8


# -------------------------------------------------------------------
# Persistence
# -------------------------------------------------------------------


def save_package(pkg: Dict[str, Any]) -> None:
    pkg = dict(pkg)
    pkg_checksum = package_checksum(pkg)
    with SessionLocal() as db:
        try:
            package = PackageORM(
                package_id=pkg["package_id"],
                agent_id=pkg["agent_id"],
                schema_version=pkg["schema_version"],
                created_at=datetime.fromisoformat(pkg["created_at"]),
                updated_at=datetime.fromisoformat(pkg["updated_at"]),
                checksum=pkg_checksum,
                raw_package=pkg,
            )
            db.add(package)
            db.flush()

            for parent_id in pkg["lineage"]["parent_package_ids"]:
                db.add(
                    PackageLineageORM(
                        package_id=pkg["package_id"],
                        ancestor_package_id=parent_id,
                        relation_type="parent",
                    )
                )

            for ancestor_id in pkg["lineage"]["merge_ancestor_ids"]:
                db.add(
                    PackageLineageORM(
                        package_id=pkg["package_id"],
                        ancestor_package_id=ancestor_id,
                        relation_type="merge_ancestor",
                    )
                )

            upsert_state_rows(db, pkg)
            build_retrieval_chunks(db, pkg)

            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            raise RuntimeError(f"Failed to save package: {e}") from e


def get_package(package_id: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        row = db.get(PackageORM, package_id)
        return row.raw_package if row else None


def mark_current_false_for_agent(db, agent_id: str) -> None:
    db.query(FactORM).filter(FactORM.agent_id == agent_id, FactORM.is_current.is_(True)).update(
        {FactORM.is_current: False}
    )
    db.query(PreferenceORM).filter(
        PreferenceORM.agent_id == agent_id, PreferenceORM.is_current.is_(True)
    ).update({PreferenceORM.is_current: False})
    db.query(ProjectORM).filter(ProjectORM.agent_id == agent_id, ProjectORM.is_current.is_(True)).update(
        {ProjectORM.is_current: False}
    )
    db.query(ConversationSummaryORM).filter(
        ConversationSummaryORM.agent_id == agent_id, ConversationSummaryORM.is_current.is_(True)
    ).update({ConversationSummaryORM.is_current: False})


def upsert_state_rows(db, pkg: Dict[str, Any]) -> None:
    agent_id = pkg["agent_id"]
    package_id = pkg["package_id"]

    mark_current_false_for_agent(db, agent_id)

    for fact in pkg["state"]["facts"]:
        db.add(
            FactORM(
                fact_id=fact["fact_id"],
                agent_id=agent_id,
                package_id=package_id,
                fact_key=fact["key"],
                fact_value=fact["value"],
                status=fact["status"],
                provenance=fact["provenance"],
                updated_at=datetime.fromisoformat(fact["updated_at"]),
                is_current=True,
            )
        )

    for pref in pkg["state"]["preferences"]:
        db.add(
            PreferenceORM(
                preference_id=pref["preference_id"],
                agent_id=agent_id,
                package_id=package_id,
                preference_key=pref["key"],
                preference_value=pref["value"],
                strength=pref["strength"],
                provenance=pref["provenance"],
                updated_at=datetime.fromisoformat(pref["updated_at"]),
                is_current=True,
            )
        )

    for project in pkg["state"]["projects"]:
        db.add(
            ProjectORM(
                project_id=project["project_id"],
                agent_id=agent_id,
                package_id=package_id,
                name=project["name"],
                summary=project["summary"],
                status=project["status"],
                provenance=project["provenance"],
                updated_at=datetime.fromisoformat(project["updated_at"]),
                is_current=True,
            )
        )

    for convo in pkg["state"]["conversation_summaries"]:
        db.merge(
            ConversationSummaryORM(
                conversation_id=convo["conversation_id"],
                agent_id=agent_id,
                package_id=package_id,
                title=convo["title"],
                summary=convo["summary"],
                provenance=convo["provenance"],
                updated_at=datetime.fromisoformat(convo["updated_at"]),
                is_current=True,
            )
        )

    for conflict in pkg["state"]["conflicts"]:
        db.add(
            ConflictORM(
                conflict_id=conflict["conflict_id"],
                agent_id=agent_id,
                package_id=package_id,
                state_type=conflict["state_type"],
                object_key=conflict["object_key"],
                field=conflict["field"],
                left_value=conflict["left_value"],
                right_value=conflict["right_value"],
                status=conflict["status"],
                detected_at=datetime.fromisoformat(conflict["detected_at"]),
            )
        )


# -------------------------------------------------------------------
# Retrieval
# -------------------------------------------------------------------


def build_retrieval_chunks(db, pkg: Dict[str, Any]) -> None:
    package_id = pkg["package_id"]
    agent_id = pkg["agent_id"]

    rows: List[RetrievalChunkORM] = []

    for fact in pkg["state"]["facts"]:
        rows.append(
            RetrievalChunkORM(
                chunk_id=uuid_str(),
                agent_id=agent_id,
                package_id=package_id,
                source_type="fact",
                source_id=fact["fact_id"],
                text_content=f"Fact: {fact['key']} = {fact['value']}",
                metadata_json={},
                updated_at=now_dt(),
            )
        )

    for pref in pkg["state"]["preferences"]:
        rows.append(
            RetrievalChunkORM(
                chunk_id=uuid_str(),
                agent_id=agent_id,
                package_id=package_id,
                source_type="preference",
                source_id=pref["preference_id"],
                text_content=f"Preference: {pref['key']} = {pref['value']} ({pref['strength']})",
                metadata_json={},
                updated_at=now_dt(),
            )
        )

    for project in pkg["state"]["projects"]:
        rows.append(
            RetrievalChunkORM(
                chunk_id=uuid_str(),
                agent_id=agent_id,
                package_id=package_id,
                source_type="project",
                source_id=project["project_id"],
                text_content=f"Project: {project['name']}. Status: {project['status']}. Summary: {project['summary']}",
                metadata_json={},
                updated_at=now_dt(),
            )
        )

    for convo in pkg["state"]["conversation_summaries"]:
        rows.append(
            RetrievalChunkORM(
                chunk_id=uuid_str(),
                agent_id=agent_id,
                package_id=package_id,
                source_type="conversation_summary",
                source_id=convo["conversation_id"],
                text_content=f"Conversation: {convo['title']}. Summary: {convo['summary']}",
                metadata_json={},
                updated_at=now_dt(),
            )
        )

    for row in rows:
        db.add(row)


def fetch_structured_context(agent_id: str) -> Dict[str, Any]:
    with SessionLocal() as db:
        projects = db.execute(
            select(ProjectORM)
            .where(ProjectORM.agent_id == agent_id, ProjectORM.is_current.is_(True))
            .order_by(desc(ProjectORM.updated_at))
            .limit(5)
        ).scalars().all()

        preferences = db.execute(
            select(PreferenceORM)
            .where(PreferenceORM.agent_id == agent_id, PreferenceORM.is_current.is_(True))
            .order_by(desc(PreferenceORM.updated_at))
            .limit(10)
        ).scalars().all()

        facts = db.execute(
            select(FactORM)
            .where(FactORM.agent_id == agent_id, FactORM.is_current.is_(True), FactORM.status == "active")
            .order_by(desc(FactORM.updated_at))
            .limit(20)
        ).scalars().all()

        conflicts = db.execute(
            select(ConflictORM)
            .where(ConflictORM.agent_id == agent_id, ConflictORM.status == "open")
            .order_by(desc(ConflictORM.detected_at))
            .limit(10)
        ).scalars().all()

        summaries = db.execute(
            select(ConversationSummaryORM)
            .where(ConversationSummaryORM.agent_id == agent_id, ConversationSummaryORM.is_current.is_(True))
            .order_by(desc(ConversationSummaryORM.updated_at))
            .limit(5)
        ).scalars().all()

    return {
        "projects": projects,
        "preferences": preferences,
        "facts": facts,
        "conflicts": conflicts,
        "conversation_summaries": summaries,
    }


def semantic_search(agent_id: str, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    q = normalize_text(query)
    terms = set(q.split())

    with SessionLocal() as db:
        chunks = db.execute(
            select(RetrievalChunkORM)
            .where(RetrievalChunkORM.agent_id == agent_id)
            .order_by(desc(RetrievalChunkORM.updated_at))
            .limit(200)
        ).scalars().all()

    scored: List[Dict[str, Any]] = []
    for chunk in chunks:
        text = normalize_text(chunk.text_content)
        score = sum(1 for t in terms if t in text)
        if score > 0:
            scored.append(
                {
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "text_content": chunk.text_content,
                    "score": score,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def dedupe_text_blocks(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = normalize_text(item["text"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def assemble_context_blocks(items: List[Dict[str, Any]], max_chars: int = 12000) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    total = 0
    for item in items:
        text = item["text"].strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            break
        blocks.append({"type": item["kind"], "text": text})
        total += len(text) + 2
    return blocks


def retrieve_context(agent_id: str, query: str, top_k: int = 8) -> Dict[str, Any]:
    structured = fetch_structured_context(agent_id)
    semantic_rows = semantic_search(agent_id, query, top_k=top_k)

    selected: List[Dict[str, Any]] = []

    for p in structured["projects"]:
        selected.append({"kind": "project", "priority": 100, "text": f"Project: {p.name}\nStatus: {p.status}\nSummary: {p.summary}"})

    for pref in structured["preferences"]:
        priority = 90 if pref.strength == "required" else 70
        selected.append({"kind": "preference", "priority": priority, "text": f"Preference: {pref.preference_key} = {pref.preference_value}"})

    for fact in structured["facts"][:10]:
        selected.append({"kind": "fact", "priority": 60, "text": f"Fact: {fact.fact_key} = {fact.fact_value}"})

    for row in semantic_rows:
        selected.append({"kind": "semantic", "priority": min(50 + row["score"] * 5, 95), "text": row["text_content"]})

    for c in structured["conflicts"][:5]:
        selected.append({
            "kind": "conflict",
            "priority": 80,
            "text": f"Open conflict: {c.state_type} {c.object_key} field={c.field} left={c.left_value} right={c.right_value}",
        })

    selected.sort(key=lambda x: x["priority"], reverse=True)
    selected = dedupe_text_blocks(selected)
    blocks = assemble_context_blocks(selected)
    return {"query": query, "blocks": blocks, "text": "\n\n".join(block["text"] for block in blocks)}


# -------------------------------------------------------------------
# Ingest
# -------------------------------------------------------------------


def provenance_from_message(conversation_id: str, msg: TranscriptMessage, confidence: float) -> Dict[str, Any]:
    return {
        "source_type": "chat",
        "source_id": conversation_id,
        "message_id": msg.message_id,
        "captured_at": msg.created_at or now_iso(),
        "confidence": confidence,
    }


def heuristic_extract_facts(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    lower = text.lower()

    if "real product is" in lower:
        items.append({"key": "product.core_definition", "value": text.strip()})
    if "core insight is" in lower:
        items.append({"key": "product.core_insight", "value": text.strip()})
    if "goal is" in lower:
        items.append({"key": "project.goal", "value": text.strip()})
    if "need" in lower and "json" in lower:
        items.append({"key": "system.requires_json_serialization", "value": True})
    return items


def heuristic_extract_preferences(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    lower = text.lower()

    if "be direct" in lower or "direct and grounded" in lower:
        items.append({"key": "response.style", "value": "direct_grounded", "strength": "required"})
    if "do not drift" in lower:
        items.append({"key": "response.avoid_symbolic_drift", "value": True, "strength": "required"})
    if "optimize for fastest working prototype" in lower:
        items.append({"key": "engineering.optimization_target", "value": "fastest_working_prototype", "strength": "required"})
    return items


def heuristic_extract_project(title: str, messages: List[TranscriptMessage]) -> Optional[Dict[str, str]]:
    all_text = " ".join(m.content for m in messages)
    lower = all_text.lower()
    if "portable memory" in lower or "mergeable ai memory" in lower:
        return {
            "name": title.strip() or "Portable AI Memory System",
            "summary": "Portable, persistent, mergeable AI memory system for continuity across chats and agents.",
        }
    return None


def summarize_transcript(title: str, messages: List[TranscriptMessage]) -> str:
    snippets = []
    for msg in messages[:8]:
        content = msg.content.strip().replace("\n", " ")
        if content:
            snippets.append(f"{msg.role}: {content[:200]}")
    joined = " | ".join(snippets)
    return f"{title}: {joined}"[:1200]


def dedupe_facts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        out[fact_key(item)] = item
    return list(out.values())


def dedupe_preferences(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in items:
        k = normalize_text(item["key"])
        if k not in out or item["strength"] == "required":
            out[k] = item
    return list(out.values())


def ingest_transcript(req: IngestTranscriptRequest) -> Dict[str, Any]:
    now = now_iso()
    facts: List[Dict[str, Any]] = []
    preferences: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    conversation_summaries: List[Dict[str, Any]] = []

    for msg in req.messages:
        if msg.role != "user":
            continue
        for item in heuristic_extract_facts(msg.content):
            facts.append({
                "fact_id": uuid_str(),
                "key": item["key"],
                "value": item["value"],
                "status": "active",
                "updated_at": msg.created_at or now,
                "provenance": provenance_from_message(req.conversation_id, msg, 0.85),
            })
        for item in heuristic_extract_preferences(msg.content):
            preferences.append({
                "preference_id": uuid_str(),
                "key": item["key"],
                "value": item["value"],
                "strength": item.get("strength", "strong"),
                "updated_at": msg.created_at or now,
                "provenance": provenance_from_message(req.conversation_id, msg, 0.90),
            })

    project = heuristic_extract_project(req.title, req.messages)
    if project:
        projects.append({
            "project_id": uuid_str(),
            "name": project["name"],
            "summary": project["summary"],
            "status": "active",
            "updated_at": now,
            "provenance": {
                "source_type": "chat",
                "source_id": req.conversation_id,
                "message_id": None,
                "captured_at": now,
                "confidence": 0.88,
            },
        })

    summary_text = summarize_transcript(req.title, req.messages)
    conversation_summaries.append({
        "conversation_id": req.conversation_id,
        "title": req.title,
        "summary": summary_text,
        "updated_at": now,
        "provenance": {
            "source_type": "chat",
            "source_id": req.conversation_id,
            "message_id": None,
            "captured_at": now,
            "confidence": 0.92,
        },
    })

    pkg = {
        "schema_version": "0.1.0",
        "package_id": uuid_str(),
        "agent_id": req.agent_id,
        "created_at": now,
        "updated_at": now,
        "lineage": {"parent_package_ids": [], "merge_ancestor_ids": []},
        "state": {
            "facts": dedupe_facts(facts),
            "preferences": dedupe_preferences(preferences),
            "projects": projects,
            "conversation_summaries": conversation_summaries,
            "conflicts": [],
        },
    }

    save_package(pkg)
    return {
        "package_id": pkg["package_id"],
        "counts": {
            "facts": len(pkg["state"]["facts"]),
            "preferences": len(pkg["state"]["preferences"]),
            "projects": len(pkg["state"]["projects"]),
            "conversation_summaries": len(pkg["state"]["conversation_summaries"]),
        },
    }


# -------------------------------------------------------------------
# Merge logic
# -------------------------------------------------------------------


def fact_equivalent(base: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return json_equal(base["value"], item["value"]) and base["status"] == item["status"]


def preference_equivalent(base: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return json_equal(base["value"], item["value"]) and base["strength"] == item["strength"]


def convo_equivalent(base: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return normalize_text(base["summary"]) == normalize_text(item["summary"])


STRENGTH_ORDER = {"weak": 1, "strong": 2, "required": 3}


def stronger_strength(left: str, right: str) -> str:
    return left if STRENGTH_ORDER[left] >= STRENGTH_ORDER[right] else right


def merge_fact(base: Optional[Dict[str, Any]], left: Dict[str, Any], right: Dict[str, Any]):
    conflicts: List[Dict[str, Any]] = []
    if json_equal(left["value"], right["value"]) and left["status"] == right["status"]:
        merged = newer_of(left, right)
        merged["provenance"] = merge_provenance(left["provenance"], right["provenance"])
        return merged, conflicts

    if base is not None:
        left_changed = not fact_equivalent(base, left)
        right_changed = not fact_equivalent(base, right)
        if left_changed and not right_changed:
            return left, conflicts
        if right_changed and not left_changed:
            return right, conflicts
        if not left_changed and not right_changed:
            return base, conflicts

    if left["status"] == "retracted" and right["status"] != "retracted":
        return left, conflicts
    if right["status"] == "retracted" and left["status"] != "retracted":
        return right, conflicts

    merged = dict(newer_of(left, right))
    merged["status"] = "uncertain"
    conflicts.append(make_conflict("fact", left["key"], "value", left["value"], right["value"]))
    return merged, conflicts


def merge_preference(base: Optional[Dict[str, Any]], left: Dict[str, Any], right: Dict[str, Any]):
    conflicts: List[Dict[str, Any]] = []
    if json_equal(left["value"], right["value"]):
        merged = newer_of(left, right)
        merged["strength"] = stronger_strength(left["strength"], right["strength"])
        merged["provenance"] = merge_provenance(left["provenance"], right["provenance"])
        return merged, conflicts

    if base is not None:
        left_changed = not preference_equivalent(base, left)
        right_changed = not preference_equivalent(base, right)
        if left_changed and not right_changed:
            return left, conflicts
        if right_changed and not left_changed:
            return right, conflicts

    if is_newer(left, right) and STRENGTH_ORDER[left["strength"]] >= STRENGTH_ORDER[right["strength"]]:
        return left, conflicts
    if is_newer(right, left) and STRENGTH_ORDER[right["strength"]] >= STRENGTH_ORDER[left["strength"]]:
        return right, conflicts

    conflicts.append(make_conflict("preference", left["key"], "value", left["value"], right["value"]))
    return dict(newer_of(left, right)), conflicts


def merge_project(base: Optional[Dict[str, Any]], left: Dict[str, Any], right: Dict[str, Any]):
    conflicts: List[Dict[str, Any]] = []
    merged = dict(newer_of(left, right))

    if normalize_text(left["name"]) != normalize_text(right["name"]):
        conflicts.append(make_conflict("project", left.get("project_id") or left["name"], "name", left["name"], right["name"]))

    merged["summary"] = left["summary"] if is_newer(left, right) else right["summary"]

    if left["status"] == right["status"]:
        merged["status"] = left["status"]
        return merged, conflicts

    if base is not None:
        left_changed = left["status"] != base["status"]
        right_changed = right["status"] != base["status"]
        if left_changed and not right_changed:
            merged["status"] = left["status"]
            return merged, conflicts
        if right_changed and not left_changed:
            merged["status"] = right["status"]
            return merged, conflicts

    merged["status"] = left["status"] if is_newer(left, right) else right["status"]
    if {left["status"], right["status"]} == {"active", "completed"}:
        conflicts.append(make_conflict("project", left["name"], "status", left["status"], right["status"]))
    return merged, conflicts


def merge_conversation_summary(base: Optional[Dict[str, Any]], left: Dict[str, Any], right: Dict[str, Any]):
    conflicts: List[Dict[str, Any]] = []
    if base is not None:
        left_changed = not convo_equivalent(base, left)
        right_changed = not convo_equivalent(base, right)
        if left_changed and not right_changed:
            return left, conflicts
        if right_changed and not left_changed:
            return right, conflicts
    return dict(newer_of(left, right)), conflicts


def merge_collection(state_type: str, base_items: Dict[str, Dict[str, Any]], left_items: Dict[str, Dict[str, Any]], right_items: Dict[str, Dict[str, Any]], merge_item_fn):
    merged_items: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    all_keys = sorted(set(base_items) | set(left_items) | set(right_items))

    for key in all_keys:
        base_item = base_items.get(key)
        left_item = left_items.get(key)
        right_item = right_items.get(key)
        if left_item and not right_item:
            merged_items.append(left_item)
            continue
        if right_item and not left_item:
            merged_items.append(right_item)
            continue
        if left_item and right_item:
            merged_item, item_conflicts = merge_item_fn(base_item, left_item, right_item)
            if merged_item is not None:
                merged_items.append(merged_item)
            conflicts.extend(item_conflicts)
    return merged_items, conflicts


def collect_ancestors(base_pkg, left_pkg, right_pkg) -> List[str]:
    out: List[str] = []
    if base_pkg:
        out.append(base_pkg["package_id"])
    out.extend(left_pkg["lineage"].get("merge_ancestor_ids", []))
    out.extend(right_pkg["lineage"].get("merge_ancestor_ids", []))
    return unique_ids(out)


def new_empty_package(agent_id: str) -> Dict[str, Any]:
    now = now_iso()
    return {
        "schema_version": "0.1.0",
        "package_id": uuid_str(),
        "agent_id": agent_id,
        "created_at": now,
        "updated_at": now,
        "lineage": {"parent_package_ids": [], "merge_ancestor_ids": []},
        "state": {"facts": [], "preferences": [], "projects": [], "conversation_summaries": [], "conflicts": []},
    }


def merge_packages(base_pkg, left_pkg, right_pkg):
    merged = new_empty_package(agent_id=left_pkg["agent_id"])
    merged["lineage"]["parent_package_ids"] = unique_ids([left_pkg["package_id"], right_pkg["package_id"]])
    merged["lineage"]["merge_ancestor_ids"] = collect_ancestors(base_pkg, left_pkg, right_pkg)

    merged["state"]["facts"], fact_conflicts = merge_collection(
        "fact",
        index_by_key(base_pkg["state"]["facts"], fact_key) if base_pkg else {},
        index_by_key(left_pkg["state"]["facts"], fact_key),
        index_by_key(right_pkg["state"]["facts"], fact_key),
        merge_fact,
    )

    merged["state"]["preferences"], pref_conflicts = merge_collection(
        "preference",
        index_by_key(base_pkg["state"]["preferences"], preference_key) if base_pkg else {},
        index_by_key(left_pkg["state"]["preferences"], preference_key),
        index_by_key(right_pkg["state"]["preferences"], preference_key),
        merge_preference,
    )

    merged["state"]["projects"], project_conflicts = merge_collection(
        "project",
        index_by_key(base_pkg["state"]["projects"], project_key) if base_pkg else {},
        index_by_key(left_pkg["state"]["projects"], project_key),
        index_by_key(right_pkg["state"]["projects"], project_key),
        merge_project,
    )

    merged["state"]["conversation_summaries"], convo_conflicts = merge_collection(
        "conversation_summary",
        index_by_key(base_pkg["state"]["conversation_summaries"], conversation_key) if base_pkg else {},
        index_by_key(left_pkg["state"]["conversation_summaries"], conversation_key),
        index_by_key(right_pkg["state"]["conversation_summaries"], conversation_key),
        merge_conversation_summary,
    )

    merged["state"]["conflicts"] = fact_conflicts + pref_conflicts + project_conflicts + convo_conflicts
    merged["updated_at"] = now_iso()
    return merged


def preview_merge(base_package_id: Optional[str], left_package_id: str, right_package_id: str):
    base_pkg = get_package(base_package_id) if base_package_id else None
    left_pkg = get_package(left_package_id)
    right_pkg = get_package(right_package_id)
    if not left_pkg or not right_pkg:
        raise HTTPException(status_code=404, detail="Left or right package not found")

    merged = merge_packages(base_pkg, left_pkg, right_pkg)
    objects_examined = sum(len(x) for x in [merged["state"]["facts"], merged["state"]["preferences"], merged["state"]["projects"], merged["state"]["conversation_summaries"]])
    return {
        "mergeable": True,
        "summary": {"objects_examined": objects_examined, "objects_merged": objects_examined, "conflicts_created": len(merged["state"]["conflicts"])},
        "conflicts": merged["state"]["conflicts"],
        "merged_package_preview": merged,
    }


def execute_merge(base_package_id: Optional[str], left_package_id: str, right_package_id: str):
    result = preview_merge(base_package_id, left_package_id, right_package_id)
    merged = result["merged_package_preview"]
    save_package(merged)
    return {"merged_package_id": merged["package_id"], "conflicts": merged["state"]["conflicts"], "summary": result["summary"]}


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/v1/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "database_url": DATABASE_URL}


@app.post("/v1/packages")
def create_package(pkg: MemoryPackage):
    save_package(pkg.model_dump())
    return {"package_id": pkg.package_id, "status": "created"}


@app.get("/v1/packages/{package_id}")
def read_package(package_id: str):
    pkg = get_package(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@app.get("/v1/packages/{package_id}/export")
def export_package(package_id: str):
    pkg = get_package(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@app.post("/v1/merge/preview")
def merge_preview_route(req: MergeRequest):
    return preview_merge(req.base_package_id, req.left_package_id, req.right_package_id)


@app.post("/v1/merge")
def merge_execute_route(req: MergeRequest):
    return execute_merge(req.base_package_id, req.left_package_id, req.right_package_id)


@app.post("/v1/ingest/transcript")
def ingest_chat_transcript(req: IngestTranscriptRequest):
    return ingest_transcript(req)


@app.post("/v1/retrieve/context")
def build_context(req: RetrieveRequest):
    return retrieve_context(req.agent_id, req.query, req.top_k)
