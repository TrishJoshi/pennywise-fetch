from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "pennywise_transactions"

    id = Column(Integer, primary_key=True, index=True) # Source ID
    amount = Column(Numeric(precision=20, scale=2), nullable=True) # BigDecimal
    merchant_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    transaction_type = Column(String, nullable=True) # Enum
    date_time = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    sms_body = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    sms_sender = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    balance_after = Column(Numeric(precision=20, scale=2), nullable=True)
    transaction_hash = Column(String, unique=True, index=True)
    is_recurring = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    currency = Column(String, default="INR")
    from_account = Column(String, nullable=True)
    to_account = Column(String, nullable=True)

class Category(Base):
    __tablename__ = "pennywise_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, nullable=True)
    is_system = Column(Boolean, default=False)
    is_income = Column(Boolean, default=False)
    display_order = Column(Integer, default=999)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

class Card(Base):
    __tablename__ = "pennywise_cards"

    id = Column(Integer, primary_key=True, index=True)
    card_last4 = Column(String, nullable=True)
    card_type = Column(String, nullable=True) # Enum
    bank_name = Column(String, nullable=True)
    account_last4 = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_balance = Column(Numeric(precision=20, scale=2), nullable=True)
    last_balance_source = Column(String, nullable=True)
    last_balance_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    currency = Column(String, default="INR")

class AccountBalance(Base):
    __tablename__ = "pennywise_account_balances"

    id = Column(Integer, primary_key=True, index=True)
    bank_name = Column(String, nullable=False)
    account_last4 = Column(String, nullable=False)
    balance = Column(Numeric(precision=20, scale=2), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    transaction_id = Column(Integer, nullable=True)
    credit_limit = Column(Numeric(precision=20, scale=2), nullable=True)
    is_credit_card = Column(Boolean, default=False)
    sms_source = Column(String, nullable=True)
    source_type = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    currency = Column(String, default="INR")

class Subscription(Base):
    __tablename__ = "pennywise_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_name = Column(String, nullable=False)
    amount = Column(Numeric(precision=20, scale=2), nullable=True)
    next_payment_date = Column(DateTime, nullable=True)
    state = Column(String, nullable=True) # Enum
    bank_name = Column(String, nullable=True)
    umn = Column(String, nullable=True)
    category = Column(String, nullable=True)
    sms_body = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    currency = Column(String, default="INR")

class MerchantMapping(Base):
    __tablename__ = "pennywise_merchant_mappings"

    merchant_name = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

class UnrecognizedSms(Base):
    __tablename__ = "pennywise_unrecognized_sms"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, nullable=False)
    sms_body = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=True)
    reported = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)

class ChatMessage(Base):
    __tablename__ = "pennywise_chat_messages"

    id = Column(String, primary_key=True) # UUID
    message = Column(String, nullable=False)
    isUser = Column(Boolean, default=False)
    timestamp = Column(Integer, nullable=True) # Unix Epoch Millis
    isSystemPrompt = Column(Boolean, default=False)

class TransactionRule(Base):
    __tablename__ = "pennywise_transaction_rules"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    priority = Column(Integer, nullable=False)
    conditions = Column(Text, nullable=True) # JSON String
    actions = Column(Text, nullable=True) # JSON String
    is_active = Column(Boolean, default=True)
    is_system_template = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

class RuleApplication(Base):
    __tablename__ = "pennywise_rule_applications"

    id = Column(String, primary_key=True)
    rule_id = Column(String, ForeignKey("pennywise_transaction_rules.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String, nullable=False)
    transaction_id = Column(String, nullable=False) # Note: Source schema says transaction_id is TEXT here, but transactions.id is INTEGER. Assuming it refers to transactions.id but stored as text or maybe transaction_hash? The schema report says "transaction_id -> transactions(id)". I will keep it as String to match source schema definition "TEXT" but it might be an Integer cast to string.
    fields_modified = Column(Text, nullable=True) # JSON String
    applied_at = Column(DateTime, nullable=True)

class ExchangeRate(Base):
    __tablename__ = "pennywise_exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Numeric(precision=20, scale=6), nullable=True)
    provider = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_at_unix = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    expires_at_unix = Column(Integer, default=0)

# --- Import History Models ---

class ImportLog(Base):
    __tablename__ = "pennywise_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False) # STARTED, COMPLETED, FAILED
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    row_logs = relationship("ImportRowLog", back_populates="log")

class ImportRowLog(Base):
    __tablename__ = "pennywise_import_row_logs"

    id = Column(Integer, primary_key=True, index=True)
    import_log_id = Column(Integer, ForeignKey("pennywise_import_logs.id"))
    action = Column(String, nullable=False) # ADDED, UPDATED, SKIPPED
    table_name = Column(String, nullable=False)
    
    # Foreign Keys to all entities
    transaction_id = Column(Integer, ForeignKey("pennywise_transactions.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("pennywise_categories.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("pennywise_cards.id"), nullable=True)
    account_balance_id = Column(Integer, ForeignKey("pennywise_account_balances.id"), nullable=True)
    subscription_id = Column(Integer, ForeignKey("pennywise_subscriptions.id"), nullable=True)
    merchant_mapping_id = Column(String, ForeignKey("pennywise_merchant_mappings.merchant_name"), nullable=True)
    unrecognized_sms_id = Column(Integer, ForeignKey("pennywise_unrecognized_sms.id"), nullable=True)
    chat_message_id = Column(String, ForeignKey("pennywise_chat_messages.id"), nullable=True)
    transaction_rule_id = Column(String, ForeignKey("pennywise_transaction_rules.id"), nullable=True)
    rule_application_id = Column(String, ForeignKey("pennywise_rule_applications.id"), nullable=True)
    exchange_rate_id = Column(Integer, ForeignKey("pennywise_exchange_rates.id"), nullable=True)

    log = relationship("ImportLog", back_populates="row_logs")
    
    # Relationships to entities (optional, but good for ORM access)
    transaction = relationship("Transaction")
    category = relationship("Category")
    card = relationship("Card")
    account_balance = relationship("AccountBalance")
    subscription = relationship("Subscription")
    merchant_mapping = relationship("MerchantMapping")
    unrecognized_sms = relationship("UnrecognizedSms")
    chat_message = relationship("ChatMessage")
    transaction_rule = relationship("TransactionRule")
    rule_application = relationship("RuleApplication")
    exchange_rate = relationship("ExchangeRate")
