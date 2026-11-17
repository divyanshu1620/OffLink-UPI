from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    BigInteger,
    Index
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./upimesh.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AccountTable(Base):
    __tablename__ = "accounts"

    vpa = Column(String, primary_key=True, index=True)
    holder_name = Column(String, nullable=False)
    balance = Column(Float, nullable=False)
    version = Column(Integer, default=0, nullable=False)  # Optimistic locking equivalent to @Version

class TransactionTable(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    packet_hash = Column(String(64), unique=True, nullable=False, index=True)
    sender_vpa = Column(String, nullable=False)
    receiver_vpa = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    signed_at = Column(BigInteger, nullable=False)
    settled_at = Column(BigInteger, nullable=False)
    bridge_node_id = Column(String, nullable=False)
    hop_count = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # SETTLED or REJECTED

# Create all tables on startup
Base.metadata.create_all(bind=engine)

def seed_database():
    """Seeds the 4 default accounts matching DemoService.java."""
    db = SessionLocal()
    try:
        if db.query(AccountTable).count() == 0:
            defaults = [
                AccountTable(vpa="alice@demo", holder_name="Alice", balance=5000.0, version=0),
                AccountTable(vpa="bob@demo",   holder_name="Bob",   balance=1000.0, version=0),
                AccountTable(vpa="carol@demo", holder_name="Carol", balance=2500.0, version=0),
                AccountTable(vpa="dave@demo",  holder_name="Dave",  balance=500.0,  version=0),
            ]
            db.add_all(defaults)
            db.commit()
    finally:
        db.close()