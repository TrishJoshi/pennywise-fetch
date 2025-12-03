from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

# --- Entity Schemas ---

class TransactionEntity(BaseModel):
    id: Optional[int] = None
    amount: Optional[str] = None
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    transaction_type: Optional[str] = None
    date_time: Optional[str] = None
    description: Optional[str] = None
    sms_body: Optional[str] = None
    bank_name: Optional[str] = None
    sms_sender: Optional[str] = None
    account_number: Optional[str] = None
    balance_after: Optional[str] = None
    transaction_hash: Optional[str] = None
    is_recurring: Optional[int] = None # 0 or 1
    is_deleted: Optional[int] = None # 0 or 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    currency: Optional[str] = None
    from_account: Optional[str] = None
    to_account: Optional[str] = None

class CategoryEntity(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    color: Optional[str] = None
    is_system: Optional[int] = None
    is_income: Optional[int] = None
    display_order: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CardEntity(BaseModel):
    id: Optional[int] = None
    card_last4: Optional[str] = None
    card_type: Optional[str] = None
    bank_name: Optional[str] = None
    account_last4: Optional[str] = None
    nickname: Optional[str] = None
    is_active: Optional[int] = None
    last_balance: Optional[str] = None
    last_balance_source: Optional[str] = None
    last_balance_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    currency: Optional[str] = None

class AccountBalanceEntity(BaseModel):
    id: Optional[int] = None
    bank_name: Optional[str] = None
    account_last4: Optional[str] = None
    balance: Optional[str] = None
    timestamp: Optional[str] = None
    transaction_id: Optional[int] = None
    credit_limit: Optional[str] = None
    is_credit_card: Optional[int] = None
    sms_source: Optional[str] = None
    source_type: Optional[str] = None
    created_at: Optional[str] = None
    currency: Optional[str] = None

class SubscriptionEntity(BaseModel):
    id: Optional[int] = None
    merchant_name: Optional[str] = None
    amount: Optional[str] = None
    next_payment_date: Optional[str] = None
    state: Optional[str] = None
    bank_name: Optional[str] = None
    umn: Optional[str] = None
    category: Optional[str] = None
    sms_body: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    currency: Optional[str] = None

class MerchantMappingEntity(BaseModel):
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class UnrecognizedSmsEntity(BaseModel):
    id: Optional[int] = None
    sender: Optional[str] = None
    sms_body: Optional[str] = None
    received_at: Optional[str] = None
    reported: Optional[int] = None
    is_deleted: Optional[int] = None
    created_at: Optional[str] = None

class ChatMessageEntity(BaseModel):
    id: Optional[str] = None
    message: Optional[str] = None
    isUser: Optional[int] = None
    timestamp: Optional[int] = None
    isSystemPrompt: Optional[int] = None

class TransactionRuleEntity(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    conditions: Optional[str] = None
    actions: Optional[str] = None
    is_active: Optional[int] = None
    is_system_template: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class RuleApplicationEntity(BaseModel):
    id: Optional[str] = None
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    transaction_id: Optional[str] = None
    fields_modified: Optional[str] = None
    applied_at: Optional[str] = None

class ExchangeRateEntity(BaseModel):
    id: Optional[int] = None
    from_currency: Optional[str] = None
    to_currency: Optional[str] = None
    rate: Optional[str] = None
    provider: Optional[str] = None
    updated_at: Optional[str] = None
    updated_at_unix: Optional[int] = None
    expires_at: Optional[str] = None
    expires_at_unix: Optional[int] = None

# --- Snapshot Schemas ---

class DatabaseSnapshot(BaseModel):
    transactions: List[TransactionEntity] = []
    categories: List[CategoryEntity] = []
    cards: List[CardEntity] = []
    account_balances: List[AccountBalanceEntity] = []
    subscriptions: List[SubscriptionEntity] = []
    merchant_mappings: List[MerchantMappingEntity] = []
    unrecognized_sms: List[UnrecognizedSmsEntity] = []
    chat_messages: List[ChatMessageEntity] = []
    transaction_rules: List[TransactionRuleEntity] = []
    rule_applications: List[RuleApplicationEntity] = []
    exchange_rates: List[ExchangeRateEntity] = []

class MetadataSnapshot(BaseModel):
    export_id: Optional[str] = None
    app_version: Optional[str] = None
    database_version: Optional[int] = None
    device: Optional[str] = None
    android_version: Optional[int] = None
    statistics: Optional[Dict[str, Any]] = None

class PreferencesSnapshot(BaseModel):
    theme: Optional[Dict[str, Any]] = None
    sms: Optional[Dict[str, Any]] = None
    developer: Optional[Dict[str, Any]] = None
    app: Optional[Dict[str, Any]] = None

class PennyWiseBackup(BaseModel):
    format: Optional[str] = Field(None, alias="_format")
    warning: Optional[str] = Field(None, alias="_warning")
    created: Optional[str] = Field(None, alias="_created")
    metadata: Optional[MetadataSnapshot] = None
    database: Optional[DatabaseSnapshot] = None
    preferences: Optional[PreferencesSnapshot] = None
