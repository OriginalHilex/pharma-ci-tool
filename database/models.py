from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Company(Base):
    """Pharmaceutical/biotech company."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    ticker: Mapped[Optional[str]] = mapped_column(String(10))
    description: Mapped[Optional[str]] = mapped_column(Text)
    website: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    assets: Mapped[list["Asset"]] = relationship(back_populates="company")


class Asset(Base):
    """Drug asset being tracked."""
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(255))
    generic_name: Mapped[Optional[str]] = mapped_column(String(255))
    mechanism_of_action: Mapped[Optional[str]] = mapped_column(Text)
    stage: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., Phase 3, Approved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="assets")
    indications: Mapped[list["AssetIndication"]] = relationship(back_populates="asset")
    clinical_trials: Mapped[list["ClinicalTrial"]] = relationship(back_populates="asset")
    publications: Mapped[list["Publication"]] = relationship(back_populates="asset")
    news_articles: Mapped[list["NewsArticle"]] = relationship(back_populates="asset")
    patents: Mapped[list["Patent"]] = relationship(back_populates="asset")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_company_asset"),
    )


class Indication(Base):
    """Medical indication/disease area."""
    __tablename__ = "indications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    therapeutic_area: Mapped[Optional[str]] = mapped_column(String(255))
    icd_code: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    assets: Mapped[list["AssetIndication"]] = relationship(back_populates="indication")
    clinical_trials: Mapped[list["ClinicalTrial"]] = relationship(back_populates="indication")


class AssetIndication(Base):
    """Many-to-many relationship between assets and indications."""
    __tablename__ = "asset_indications"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    indication_id: Mapped[int] = mapped_column(ForeignKey("indications.id"), primary_key=True)
    status: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., Approved, Phase 3
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    asset: Mapped["Asset"] = relationship(back_populates="indications")
    indication: Mapped["Indication"] = relationship(back_populates="assets")


class ClinicalTrial(Base):
    """Clinical trial from ClinicalTrials.gov."""
    __tablename__ = "clinical_trials"

    id: Mapped[int] = mapped_column(primary_key=True)
    nct_id: Mapped[str] = mapped_column(String(20), unique=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"))
    indication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("indications.id"))
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String(50))
    phase: Mapped[Optional[str]] = mapped_column(String(20))
    start_date: Mapped[Optional[datetime]] = mapped_column(Date)
    completion_date: Mapped[Optional[datetime]] = mapped_column(Date)
    enrollment: Mapped[Optional[int]] = mapped_column(Integer)
    primary_endpoint: Mapped[Optional[str]] = mapped_column(Text)
    results_summary: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(512))
    sponsor: Mapped[Optional[str]] = mapped_column(String(255))
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    asset: Mapped[Optional["Asset"]] = relationship(back_populates="clinical_trials")
    indication: Mapped[Optional["Indication"]] = relationship(back_populates="clinical_trials")

    __table_args__ = (
        Index("ix_clinical_trials_status", "status"),
        Index("ix_clinical_trials_phase", "phase"),
    )


class Publication(Base):
    """Publication from PubMed."""
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    pmid: Mapped[str] = mapped_column(String(20), unique=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"))
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[Optional[str]] = mapped_column(Text)
    journal: Mapped[Optional[str]] = mapped_column(String(255))
    publication_date: Mapped[Optional[datetime]] = mapped_column(Date)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    doi: Mapped[Optional[str]] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(512))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    asset: Mapped[Optional["Asset"]] = relationship(back_populates="publications")

    __table_args__ = (
        Index("ix_publications_publication_date", "publication_date"),
    )


class NewsArticle(Base):
    """News article from Google News."""
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"))
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    asset: Mapped[Optional["Asset"]] = relationship(back_populates="news_articles")

    __table_args__ = (
        Index("ix_news_articles_published_at", "published_at"),
    )


class Patent(Base):
    """Patent from Google Patents."""
    __tablename__ = "patents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patent_number: Mapped[str] = mapped_column(String(50), unique=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"))
    title: Mapped[str] = mapped_column(Text)
    assignee: Mapped[Optional[str]] = mapped_column(String(255))
    filing_date: Mapped[Optional[datetime]] = mapped_column(Date)
    grant_date: Mapped[Optional[datetime]] = mapped_column(Date)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    claims_count: Mapped[Optional[int]] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String(512))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    asset: Mapped[Optional["Asset"]] = relationship(back_populates="patents")

    __table_args__ = (
        Index("ix_patents_filing_date", "filing_date"),
    )
