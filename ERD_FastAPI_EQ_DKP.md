# Entity Relationship Diagram (ERD)
# EQ DKP FastAPI Database Design

## Database Schema Overview

This ERD defines the database structure for the FastAPI-based EQ DKP system using SQLAlchemy ORM models, focusing on the core entities needed for guild roster management, DKP tracking, events, raids, and loot distribution. Database migrations are managed using Alembic.

## SQLAlchemy ORM Models

### 1. Users Model
**Purpose**: Store Discord user account information and OAuth data

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.schema import CheckConstraint, Index
from datetime import datetime
from enum import Enum
import uuid

Base = declarative_base()

class RoleGroup(str, Enum):
    OFFICER = "officer"
    RECRUITER = "recruiter"
    DEVELOPER = "developer"
    MEMBER = "member"
    APPLICANT = "applicant"
    GUEST = "guest"

class MembershipStatus(str, Enum):
    MEMBER = "member"
    TRIAL = "trial"
    APPLICANT = "applicant"
    INACTIVE = "inactive"

class User(Base):
    """Discord user account information and OAuth data"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String(50), unique=True, nullable=False, index=True)
    discord_username = Column(String(50), nullable=False, index=True)
    discord_discriminator = Column(String(10), nullable=True)  # Legacy Discord discriminators
    discord_global_name = Column(String(50), nullable=True)   # New Discord display names
    discord_avatar = Column(String(255), nullable=True)       # Discord avatar hash/URL
    discord_email = Column(String(255), nullable=True)        # Email from Discord OAuth
    
    role_group = Column(String(20), default=RoleGroup.GUEST, nullable=False, index=True)
    membership_status = Column(String(20), default=MembershipStatus.APPLICANT, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # OAuth token storage
    discord_access_token = Column(Text, nullable=True)
    discord_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True, index=True)
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("LENGTH(discord_id) >= 10", name="users_discord_id_length"),
        CheckConstraint("LENGTH(discord_username) >= 2", name="users_discord_username_length"),
        CheckConstraint(
            f"role_group IN ('{RoleGroup.OFFICER}', '{RoleGroup.RECRUITER}', '{RoleGroup.DEVELOPER}', "
            f"'{RoleGroup.MEMBER}', '{RoleGroup.APPLICANT}', '{RoleGroup.GUEST}')",
            name="users_role_group_valid"
        ),
        CheckConstraint(
            f"membership_status IN ('{MembershipStatus.MEMBER}', '{MembershipStatus.TRIAL}', "
            f"'{MembershipStatus.APPLICANT}', '{MembershipStatus.INACTIVE}')",
            name="users_membership_status_valid"
        ),
        Index('idx_users_discord_id', 'discord_id'),
        Index('idx_users_discord_username', 'discord_username'),
        Index('idx_users_role_group', 'role_group'),
        Index('idx_users_membership_status', 'membership_status'),
        Index('idx_users_active', 'is_active'),
        Index('idx_users_last_login', 'last_login'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, discord_username='{self.discord_username}', discord_id='{self.discord_id}')>"
```

### 2. API Keys Model
**Purpose**: Store API keys for user and bot programmatic access

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint, Index

class KeyType(str, Enum):
    PERSONAL = "personal"
    BOT = "bot"

class APIKey(Base):
    """API keys for user and bot programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    key_name = Column(String(100), nullable=False)  # User-defined name for the key
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # Hashed API key
    key_prefix = Column(String(20), nullable=False, index=True)  # First few characters for identification
    key_type = Column(String(20), default=KeyType.PERSONAL, nullable=False, index=True)
    permissions = Column(ARRAY(String), default=[], nullable=False)  # Array of permission scopes
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_used_at = Column(DateTime, nullable=True, index=True)
    usage_count = Column(Integer, default=0, nullable=False)
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # For bot keys
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="api_keys")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_api_keys")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("LENGTH(key_name) >= 3", name="api_keys_name_length"),
        CheckConstraint(
            f"key_type IN ('{KeyType.PERSONAL}', '{KeyType.BOT}')",
            name="api_keys_type_valid"
        ),
        CheckConstraint(
            "(key_type = 'personal' AND user_id IS NOT NULL) OR (key_type = 'bot' AND created_by IS NOT NULL)",
            name="api_keys_user_or_bot"
        ),
        Index('idx_api_keys_user', 'user_id'),
        Index('idx_api_keys_hash', 'key_hash'),
        Index('idx_api_keys_prefix', 'key_prefix'),
        Index('idx_api_keys_type', 'key_type'),
        Index('idx_api_keys_active', 'is_active'),
        Index('idx_api_keys_created_by', 'created_by'),
        Index('idx_api_keys_last_used', 'last_used_at'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, key_name='{self.key_name}', key_type='{self.key_type}')>"

# Add reverse relationships to User model
User.api_keys = relationship("APIKey", foreign_keys="APIKey.user_id", back_populates="user")
User.created_api_keys = relationship("APIKey", foreign_keys="APIKey.created_by", back_populates="creator")
```

### 3. Characters Model
**Purpose**: Store character information and link to users

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint, Index

class Character(Base):
    """Character information linked to users"""
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    character_class = Column(String(50), nullable=True)
    level = Column(Integer, default=1, nullable=False)
    is_main = Column(Boolean, default=False, nullable=False)
    main_character_id = Column(Integer, ForeignKey("characters.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="characters")
    main_character = relationship("Character", remote_side=[id], back_populates="alts")
    alts = relationship("Character", back_populates="main_character")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 120", name="characters_level_range"),
        CheckConstraint("LENGTH(name) >= 2", name="characters_name_length"),
        CheckConstraint("main_character_id != id", name="characters_main_not_self"),
        Index('idx_characters_name', 'name'),
        Index('idx_characters_user_id', 'user_id'),
        Index('idx_characters_main_id', 'main_character_id'),
        Index('idx_characters_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Character(id={self.id}, name='{self.name}', user_id={self.user_id})>"

# Add reverse relationship to User model
User.characters = relationship("Character", back_populates="user")
```


### 4. Additional Models
**Note**: The remaining models (DKP Pools, Events, Raids, Items, etc.) follow the same SQLAlchemy pattern with proper relationships, constraints, and indexes. For brevity, they are not all shown here, but would include:

- DKPPool, Event, Raid, RaidAttendance
- Item, ItemBid, BidHistory, LootDistribution  
- PointAdjustment, UserPointsSummary
- CharacterOwnershipHistory, DiscordSyncLog
- GuildApplication, ApplicationVote, ApplicationComment, MemberAttendanceSummary

### 5. DKP Pools Table
**Purpose**: Define different DKP pools (e.g., Main Raid, Alt Raid, etc.)

```sql
CREATE TABLE dkp_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT dkp_pools_name_length CHECK (LENGTH(name) >= 2)
);

-- Indexes
CREATE INDEX idx_dkp_pools_active ON dkp_pools(is_active);
```

### 6. Events Table
**Purpose**: Define types of raids/events that award points

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    default_points DECIMAL(10,2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT events_name_length CHECK (LENGTH(name) >= 2),
    CONSTRAINT events_points_positive CHECK (default_points >= 0)
);

-- Indexes
CREATE INDEX idx_events_name ON events(name);
CREATE INDEX idx_events_active ON events(is_active);
```

### 7. Raids Table
**Purpose**: Store specific instances of events where points are awarded

```sql
CREATE TABLE raids (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    name VARCHAR(200) NOT NULL,
    raid_date TIMESTAMP NOT NULL,
    points_awarded DECIMAL(10,2) DEFAULT 0.00,
    notes TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT raids_points_positive CHECK (points_awarded >= 0),
    CONSTRAINT raids_name_length CHECK (LENGTH(name) >= 2)
);

-- Indexes
CREATE INDEX idx_raids_event_id ON raids(event_id);
CREATE INDEX idx_raids_date ON raids(raid_date);
CREATE INDEX idx_raids_created_by ON raids(created_by);
```

### 8. Raid Attendance Table
**Purpose**: Award points to Discord users based on character attendance (no hard character links)

```sql
CREATE TABLE raid_attendance (
    id SERIAL PRIMARY KEY,
    raid_id INTEGER NOT NULL REFERENCES raids(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- Points awarded to Discord user
    dkp_pool_id INTEGER NOT NULL REFERENCES dkp_pools(id) ON DELETE RESTRICT,
    
    -- Character reference data (snapshot, no foreign key constraint)
    character_name VARCHAR(50) NOT NULL,  -- Character name at time of attendance
    character_class VARCHAR(50),  -- Character class for reference
    character_level INTEGER,  -- Character level at time of raid
    
    -- Attendance details
    points_earned DECIMAL(10,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'present',  -- present, late, early_leave, absent
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT raid_attendance_unique UNIQUE (raid_id, user_id, character_name, dkp_pool_id),
    CONSTRAINT raid_attendance_points_positive CHECK (points_earned >= 0),
    CONSTRAINT raid_attendance_status_valid CHECK (status IN ('present', 'late', 'early_leave', 'absent')),
    CONSTRAINT raid_attendance_char_name_length CHECK (LENGTH(character_name) >= 2)
);

-- Indexes
CREATE INDEX idx_raid_attendance_raid ON raid_attendance(raid_id);
CREATE INDEX idx_raid_attendance_user ON raid_attendance(user_id);
CREATE INDEX idx_raid_attendance_pool ON raid_attendance(dkp_pool_id);
CREATE INDEX idx_raid_attendance_char_name ON raid_attendance(character_name);
CREATE INDEX idx_raid_attendance_char_class ON raid_attendance(character_class);
```

### 9. Items Table
**Purpose**: Store information about items (no fixed costs - all awarded via bidding)

```sql
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT items_name_length CHECK (LENGTH(name) >= 2)
);

-- Indexes
CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_created_at ON items(created_at);
```

### 10. Item Bids Table
**Purpose**: Track bidding sessions and bid history for items

```sql
CREATE TABLE item_bids (
    id SERIAL PRIMARY KEY,
    raid_id INTEGER NOT NULL REFERENCES raids(id) ON DELETE RESTRICT,
    item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
    item_name VARCHAR(200) NOT NULL,  -- Snapshot in case item not in database
    bid_session_id VARCHAR(100) UNIQUE NOT NULL,  -- Discord bot generated session ID
    
    -- Bidding session info
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Winner information (Discord user focused, no hard character link)
    winning_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    winning_character_name VARCHAR(50),  -- Character name snapshot, no FK constraint
    winning_character_class VARCHAR(50),  -- Character class for reference
    winning_bid_amount DECIMAL(10,2),
    
    -- Session metadata
    created_by_bot BOOLEAN DEFAULT TRUE,
    notes TEXT,
    
    -- Constraints
    CONSTRAINT item_bids_session_id_length CHECK (LENGTH(bid_session_id) >= 10),
    CONSTRAINT item_bids_winning_bid_positive CHECK (winning_bid_amount >= 0 OR winning_bid_amount IS NULL),
    CONSTRAINT item_bids_closed_has_winner CHECK (
        (is_active = TRUE) OR 
        (is_active = FALSE AND winning_user_id IS NOT NULL AND winning_bid_amount IS NOT NULL)
    )
);

-- Indexes
CREATE INDEX idx_item_bids_raid ON item_bids(raid_id);
CREATE INDEX idx_item_bids_item ON item_bids(item_id);
CREATE INDEX idx_item_bids_session ON item_bids(bid_session_id);
CREATE INDEX idx_item_bids_active ON item_bids(is_active);
CREATE INDEX idx_item_bids_winner ON item_bids(winning_user_id);
CREATE INDEX idx_item_bids_started ON item_bids(started_at);
CREATE INDEX idx_item_bids_closed ON item_bids(closed_at);
```

### 11. Bid History Table
**Purpose**: Track individual bids placed by Discord users (no hard character links)

```sql
CREATE TABLE bid_history (
    id SERIAL PRIMARY KEY,
    bid_session_id VARCHAR(100) NOT NULL REFERENCES item_bids(bid_session_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- Discord user placing bid
    
    -- Character reference data (snapshot, no foreign key constraint)
    character_name VARCHAR(50),  -- Character name used for bid
    character_class VARCHAR(50),  -- Character class for reference
    
    -- Bid details
    bid_amount DECIMAL(10,2) NOT NULL,
    user_balance_at_bid DECIMAL(10,2) NOT NULL,  -- User's balance when bid was placed
    is_valid BOOLEAN DEFAULT TRUE,  -- False if bid exceeded balance
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    discord_message_id VARCHAR(50),  -- Reference to Discord message
    
    -- Constraints
    CONSTRAINT bid_history_amount_positive CHECK (bid_amount > 0),
    CONSTRAINT bid_history_balance_positive CHECK (user_balance_at_bid >= 0),
    CONSTRAINT bid_history_valid_amount CHECK (
        (is_valid = FALSE) OR (is_valid = TRUE AND bid_amount <= user_balance_at_bid)
    )
);

-- Indexes
CREATE INDEX idx_bid_history_session ON bid_history(bid_session_id);
CREATE INDEX idx_bid_history_user ON bid_history(user_id);
CREATE INDEX idx_bid_history_char_name ON bid_history(character_name);
CREATE INDEX idx_bid_history_amount ON bid_history(bid_amount);
CREATE INDEX idx_bid_history_placed ON bid_history(placed_at);
CREATE INDEX idx_bid_history_valid ON bid_history(is_valid);
```

### 12. Loot Distribution Table
**Purpose**: Track final item awards from bidding results (Discord user focused, no hard character links)

```sql
CREATE TABLE loot_distribution (
    id SERIAL PRIMARY KEY,
    raid_id INTEGER NOT NULL REFERENCES raids(id) ON DELETE RESTRICT,
    bid_session_id VARCHAR(100) REFERENCES item_bids(bid_session_id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,  -- Points deducted from Discord user
    item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
    dkp_pool_id INTEGER NOT NULL REFERENCES dkp_pools(id) ON DELETE RESTRICT,
    
    -- Item and character reference data (snapshots, no FK constraints)
    item_name VARCHAR(200) NOT NULL,  -- Item name from bid results
    character_name VARCHAR(50) NOT NULL,  -- Character who received item (reference only)
    character_class VARCHAR(50),  -- Character class for reference
    points_spent DECIMAL(10,2) NOT NULL,  -- Winning bid amount
    
    -- Source tracking
    submitted_by_bot BOOLEAN DEFAULT TRUE,  -- Submitted via Discord bot API
    discord_message_id VARCHAR(50),  -- Reference to Discord announcement
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT loot_points_positive CHECK (points_spent >= 0),
    CONSTRAINT loot_item_name_length CHECK (LENGTH(item_name) >= 2)
);

-- Indexes
CREATE INDEX idx_loot_raid ON loot_distribution(raid_id);
CREATE INDEX idx_loot_bid_session ON loot_distribution(bid_session_id);
CREATE INDEX idx_loot_user ON loot_distribution(user_id);
CREATE INDEX idx_loot_item ON loot_distribution(item_id);
CREATE INDEX idx_loot_pool ON loot_distribution(dkp_pool_id);
CREATE INDEX idx_loot_item_name ON loot_distribution(item_name);
CREATE INDEX idx_loot_char_name ON loot_distribution(character_name);
CREATE INDEX idx_loot_char_class ON loot_distribution(character_class);
CREATE INDEX idx_loot_points ON loot_distribution(points_spent);
CREATE INDEX idx_loot_bot_submission ON loot_distribution(submitted_by_bot);
CREATE INDEX idx_loot_date ON loot_distribution(created_at);
```

### 13. Point Adjustments Table
**Purpose**: Track manual point adjustments to Discord user accounts (no hard character links)

```sql
CREATE TABLE point_adjustments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,  -- Points adjusted for Discord user
    dkp_pool_id INTEGER NOT NULL REFERENCES dkp_pools(id) ON DELETE RESTRICT,
    
    -- Optional character reference data (snapshot, no FK constraint)
    character_name VARCHAR(50),  -- Character name for context/reference
    character_class VARCHAR(50),  -- Character class for reference
    
    -- Adjustment details
    points_change DECIMAL(10,2) NOT NULL,  -- Can be positive or negative
    reason VARCHAR(500) NOT NULL,
    adjustment_type VARCHAR(50) DEFAULT 'manual',  -- manual, bonus, penalty, correction
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- Admin who made adjustment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT point_adjustments_reason_length CHECK (LENGTH(reason) >= 3),
    CONSTRAINT point_adjustments_type_valid CHECK (adjustment_type IN ('manual', 'bonus', 'penalty', 'correction'))
);

-- Indexes
CREATE INDEX idx_point_adjustments_user ON point_adjustments(user_id);
CREATE INDEX idx_point_adjustments_pool ON point_adjustments(dkp_pool_id);
CREATE INDEX idx_point_adjustments_char_name ON point_adjustments(character_name);
CREATE INDEX idx_point_adjustments_char_class ON point_adjustments(character_class);
CREATE INDEX idx_point_adjustments_type ON point_adjustments(adjustment_type);
CREATE INDEX idx_point_adjustments_date ON point_adjustments(created_at);
CREATE INDEX idx_point_adjustments_created_by ON point_adjustments(created_by);
```

### 14. User Points Summary Table
**Purpose**: Materialized view/table for efficient user point balance queries

```sql
CREATE TABLE user_points_summary (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dkp_pool_id INTEGER NOT NULL REFERENCES dkp_pools(id) ON DELETE CASCADE,
    total_earned DECIMAL(10,2) DEFAULT 0.00,
    total_spent DECIMAL(10,2) DEFAULT 0.00,
    total_adjustments DECIMAL(10,2) DEFAULT 0.00,
    current_balance DECIMAL(10,2) GENERATED ALWAYS AS (total_earned - total_spent + total_adjustments) STORED,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, dkp_pool_id),
    
    -- Constraints
    CONSTRAINT user_points_earned_positive CHECK (total_earned >= 0),
    CONSTRAINT user_points_spent_positive CHECK (total_spent >= 0)
);

-- Indexes
CREATE INDEX idx_user_points_user ON user_points_summary(user_id);
CREATE INDEX idx_user_points_pool ON user_points_summary(dkp_pool_id);
CREATE INDEX idx_user_points_balance ON user_points_summary(current_balance);
```

### 15. Character Ownership History Table
**Purpose**: Track character reassignments between Discord users

```sql
CREATE TABLE character_ownership_history (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    previous_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    new_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transfer_reason VARCHAR(500),
    transferred_by INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- Admin who performed transfer
    transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT ownership_different_users CHECK (previous_user_id != new_user_id OR previous_user_id IS NULL)
);

-- Indexes
CREATE INDEX idx_ownership_character ON character_ownership_history(character_id);
CREATE INDEX idx_ownership_previous_user ON character_ownership_history(previous_user_id);
CREATE INDEX idx_ownership_new_user ON character_ownership_history(new_user_id);
CREATE INDEX idx_ownership_date ON character_ownership_history(transfer_date);
CREATE INDEX idx_ownership_transferred_by ON character_ownership_history(transferred_by);
```


### 17. Discord Sync Log Table
**Purpose**: Track Discord role synchronization attempts and results

```sql
CREATE TABLE discord_sync_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    discord_id VARCHAR(50),
    action VARCHAR(50) NOT NULL,  -- role_add, role_remove, sync_full, link_user
    discord_role_id VARCHAR(50),
    status VARCHAR(20) NOT NULL,  -- success, failed, pending
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT discord_sync_action_valid CHECK (action IN ('role_add', 'role_remove', 'sync_full', 'link_user')),
    CONSTRAINT discord_sync_status_valid CHECK (status IN ('success', 'failed', 'pending'))
);

-- Indexes
CREATE INDEX idx_discord_sync_user ON discord_sync_log(user_id);
CREATE INDEX idx_discord_sync_discord_id ON discord_sync_log(discord_id);
CREATE INDEX idx_discord_sync_action ON discord_sync_log(action);
CREATE INDEX idx_discord_sync_status ON discord_sync_log(status);
CREATE INDEX idx_discord_sync_date ON discord_sync_log(created_at);
```

### 18. Guild Applications Table
**Purpose**: Store recruitment applications from prospective members

```sql
CREATE TABLE guild_applications (
    id SERIAL PRIMARY KEY,
    character_name VARCHAR(50) NOT NULL,
    character_class VARCHAR(50) NOT NULL,
    character_level INTEGER NOT NULL,
    character_server VARCHAR(50),
    discord_username VARCHAR(100),
    email VARCHAR(255) NOT NULL,
    previous_guilds TEXT,
    availability TEXT,
    timezone VARCHAR(50),
    references TEXT,
    application_text TEXT NOT NULL,
    status VARCHAR(25) DEFAULT 'submitted',  -- submitted, trial_accepted, rejected, voting_active, voting_complete, approved
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP NULL,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    trial_start_date TIMESTAMP NULL,
    trial_end_date TIMESTAMP NULL,
    voting_start_date TIMESTAMP NULL,
    voting_end_date TIMESTAMP NULL,
    discord_webhook_sent BOOLEAN DEFAULT FALSE,
    created_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Constraints
    CONSTRAINT applications_level_range CHECK (character_level >= 1 AND character_level <= 120),
    CONSTRAINT applications_status_valid CHECK (status IN ('submitted', 'trial_accepted', 'rejected', 'voting_active', 'voting_complete', 'approved')),
    CONSTRAINT applications_char_name_length CHECK (LENGTH(character_name) >= 2),
    CONSTRAINT applications_email_format CHECK (email LIKE '%@%')
);

-- Indexes
CREATE INDEX idx_applications_character_name ON guild_applications(character_name);
CREATE INDEX idx_applications_status ON guild_applications(status);
CREATE INDEX idx_applications_submitted_date ON guild_applications(submitted_at);
CREATE INDEX idx_applications_reviewed_by ON guild_applications(reviewed_by);
CREATE INDEX idx_applications_trial_dates ON guild_applications(trial_start_date, trial_end_date);
CREATE INDEX idx_applications_voting_dates ON guild_applications(voting_start_date, voting_end_date);
CREATE INDEX idx_applications_webhook_sent ON guild_applications(discord_webhook_sent);
```

### 19. Application Votes Table
**Purpose**: Track all member votes on guild applications (accept all, count only ≥15% attendance)

```sql
CREATE TABLE application_votes (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES guild_applications(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote VARCHAR(10) NOT NULL,  -- pass, fail, recycle
    attendance_percentage DECIMAL(5,2) NOT NULL,  -- voter's 30-day attendance at time of vote
    is_counted BOOLEAN GENERATED ALWAYS AS (attendance_percentage >= 15.0) STORED,  -- auto-calculated
    vote_changes INTEGER DEFAULT 0,  -- number of times user changed their vote
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT application_votes_unique UNIQUE (application_id, user_id),
    CONSTRAINT application_votes_vote_valid CHECK (vote IN ('pass', 'fail', 'recycle')),
    CONSTRAINT application_votes_attendance_positive CHECK (attendance_percentage >= 0.0),
    CONSTRAINT application_votes_changes_positive CHECK (vote_changes >= 0)
);

-- Indexes
CREATE INDEX idx_app_votes_application ON application_votes(application_id);
CREATE INDEX idx_app_votes_user ON application_votes(user_id);
CREATE INDEX idx_app_votes_vote ON application_votes(vote);
CREATE INDEX idx_app_votes_attendance ON application_votes(attendance_percentage);
CREATE INDEX idx_app_votes_counted ON application_votes(is_counted);
CREATE INDEX idx_app_votes_changes ON application_votes(vote_changes);
CREATE INDEX idx_app_votes_date ON application_votes(created_at);
```

### 20. Application Comments Table
**Purpose**: Store review comments and feedback on applications

```sql
CREATE TABLE application_comments (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES guild_applications(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    comment_text TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT TRUE,  -- internal officer comment vs. applicant feedback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT application_comments_text_length CHECK (LENGTH(comment_text) >= 5)
);

-- Indexes
CREATE INDEX idx_app_comments_application ON application_comments(application_id);
CREATE INDEX idx_app_comments_user ON application_comments(user_id);
CREATE INDEX idx_app_comments_internal ON application_comments(is_internal);
CREATE INDEX idx_app_comments_date ON application_comments(created_at);
```

### 21. Member Attendance Summary Table
**Purpose**: Track 30/60/90 day and lifetime rolling attendance percentages for voting eligibility and member performance

```sql
CREATE TABLE member_attendance_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    calculation_date DATE NOT NULL,
    
    -- 30-day metrics
    total_raids_30_days INTEGER NOT NULL DEFAULT 0,
    attended_raids_30_days INTEGER NOT NULL DEFAULT 0,
    attendance_percentage_30_days DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_30_days = 0 THEN 0.0
            ELSE ROUND((attended_raids_30_days::DECIMAL / total_raids_30_days::DECIMAL) * 100, 2)
        END
    ) STORED,
    
    -- 60-day metrics
    total_raids_60_days INTEGER NOT NULL DEFAULT 0,
    attended_raids_60_days INTEGER NOT NULL DEFAULT 0,
    attendance_percentage_60_days DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_60_days = 0 THEN 0.0
            ELSE ROUND((attended_raids_60_days::DECIMAL / total_raids_60_days::DECIMAL) * 100, 2)
        END
    ) STORED,
    
    -- 90-day metrics
    total_raids_90_days INTEGER NOT NULL DEFAULT 0,
    attended_raids_90_days INTEGER NOT NULL DEFAULT 0,
    attendance_percentage_90_days DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_90_days = 0 THEN 0.0
            ELSE ROUND((attended_raids_90_days::DECIMAL / total_raids_90_days::DECIMAL) * 100, 2)
        END
    ) STORED,
    
    -- Lifetime metrics
    total_raids_lifetime INTEGER NOT NULL DEFAULT 0,
    attended_raids_lifetime INTEGER NOT NULL DEFAULT 0,
    attendance_percentage_lifetime DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_lifetime = 0 THEN 0.0
            ELSE ROUND((attended_raids_lifetime::DECIMAL / total_raids_lifetime::DECIMAL) * 100, 2)
        END
    ) STORED,
    
    -- Voting eligibility based on 30-day attendance
    is_voting_eligible BOOLEAN GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_30_days = 0 THEN FALSE
            ELSE ROUND((attended_raids_30_days::DECIMAL / total_raids_30_days::DECIMAL) * 100, 2) >= 15.0
        END
    ) STORED,
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT attendance_summary_unique UNIQUE (user_id, calculation_date),
    CONSTRAINT attendance_30_days_valid CHECK (attended_raids_30_days <= total_raids_30_days),
    CONSTRAINT attendance_60_days_valid CHECK (attended_raids_60_days <= total_raids_60_days),
    CONSTRAINT attendance_90_days_valid CHECK (attended_raids_90_days <= total_raids_90_days),
    CONSTRAINT attendance_lifetime_valid CHECK (attended_raids_lifetime <= total_raids_lifetime),
    CONSTRAINT attendance_counts_positive CHECK (
        total_raids_30_days >= 0 AND attended_raids_30_days >= 0 AND
        total_raids_60_days >= 0 AND attended_raids_60_days >= 0 AND
        total_raids_90_days >= 0 AND attended_raids_90_days >= 0 AND
        total_raids_lifetime >= 0 AND attended_raids_lifetime >= 0
    )
);

-- Indexes
CREATE INDEX idx_attendance_summary_user ON member_attendance_summary(user_id);
CREATE INDEX idx_attendance_summary_character ON member_attendance_summary(character_id);
CREATE INDEX idx_attendance_summary_date ON member_attendance_summary(calculation_date);
CREATE INDEX idx_attendance_summary_eligible ON member_attendance_summary(is_voting_eligible);
CREATE INDEX idx_attendance_summary_30d ON member_attendance_summary(attendance_percentage_30_days);
CREATE INDEX idx_attendance_summary_60d ON member_attendance_summary(attendance_percentage_60_days);
CREATE INDEX idx_attendance_summary_90d ON member_attendance_summary(attendance_percentage_90_days);
CREATE INDEX idx_attendance_summary_lifetime ON member_attendance_summary(attendance_percentage_lifetime);
CREATE INDEX idx_attendance_summary_updated ON member_attendance_summary(last_updated);
```

## Relationship Summary

### One-to-Many Relationships:
1. **Users → Characters**: One user can have multiple characters
2. **Users → API Keys**: One user can have multiple personal API keys (for bot keys, via created_by)
3. **Characters → Characters**: One main character can have multiple alts
4. **Events → Raids**: One event type can have multiple raid instances
5. **Raids → Raid Attendance**: One raid can have multiple attendees
6. **Raids → Loot Distribution**: One raid can have multiple loot distributions
7. **Users → Raid Attendance**: One user can attend multiple raids (points awarded to user)
8. **Users → Loot Distribution**: One user can receive multiple items (points deducted from user)
9. **Users → Point Adjustments**: One user can have multiple adjustments
10. **Characters → Raid Attendance**: One character can attend multiple raids (for historical reference)
11. **Characters → Loot Distribution**: One character can receive multiple items (for historical reference)
12. **Characters → Character Ownership History**: One character can have multiple ownership transfers
13. **DKP Pools → Multiple Tables**: One pool can be referenced by attendance, loot, adjustments
14. **Users → Discord Sync Log**: One user can have multiple sync log entries
15. **Users → Guild Applications**: One recruiter can review multiple applications
16. **Guild Applications → Application Votes**: One application can have multiple votes
17. **Guild Applications → Application Comments**: One application can have multiple comments
18. **Users → Application Votes**: One member can vote on multiple applications
19. **Users → Application Comments**: One user can comment on multiple applications
20. **Users → Member Attendance Summary**: One user can have multiple attendance records
21. **Raids → Item Bids**: One raid can have multiple bidding sessions
22. **Item Bids → Bid History**: One bidding session can have multiple individual bids
23. **Users → Bid History**: One user can place bids in multiple sessions
24. **Users → Item Bids**: One user can win multiple bidding sessions

### Many-to-Many Relationships:
1. **Users ↔ Raids** (via Raid Attendance): Users can attend multiple raids via different characters, raids can have multiple users
2. **Users ↔ Items** (via Loot Distribution): Users can receive multiple items via different characters, items can go to multiple users
3. **Users ↔ Item Bids** (via Bid History): Users can bid on multiple items, items can receive bids from multiple users
4. **Members ↔ Applications** (via Application Votes): Eligible members can vote on multiple applications, applications can receive votes from multiple members

**Note**: While character names are referenced in attendance and loot tables, all relationships are fundamentally user-centric to support character transfers.

## Key Business Rules

### Data Integrity Rules:
1. Character names must be unique across the entire system
2. Each user can have only one main character per DKP pool
3. Alt characters must reference a valid main character
4. **Points are always awarded to and deducted from Discord users, never characters**
5. **Character references in transaction tables are snapshots only (no foreign key constraints)**
6. **Character ownership can be transferred without affecting point balances**
7. Points earned/spent must be non-negative
8. Only active characters can participate in raids
9. **Items have no fixed costs** - all distribution via bidding
10. **Bids cannot exceed user's current DKP balance**
11. **Bidding sessions must be associated with active raids**
12. **Only one active bid session per item per raid**
13. **Bid amounts must be positive (greater than 0)**
14. **Loot distribution requires completed bidding session**
15. Discord IDs must be unique across all users and are required for all accounts
16. Users must have exactly one role group (officer, recruiter, developer, member, applicant, guest)
17. **Guests and applicants cannot access any voting data or participate in voting**
18. **Only members, developers, recruiters, and officers can participate in application voting**
19. **Only recruiters and officers can view individual vote details and attendance breakdowns**
20. API keys must be unique and properly hashed for security
21. Personal API keys can only be created by the owning user
22. Bot API keys can only be created by officers or developers
23. Only members with ≥15% 30-day attendance can vote on applications
24. Applications must have character name and class specified
25. Trial members have time-limited membership status
26. **Characters do not have ranks, groups, or roles - only Discord users have role assignments**
27. Only recruiters can accept applicants into trial status
28. Voting periods are exactly 48 hours long
29. Members can change their vote during the voting period
30. Application summaries are posted to Discord webhook upon trial acceptance

### Authentication Rules:
1. **Discord OAuth is the only web authentication method** - no username/password login
2. All user accounts must be linked to a valid Discord ID
3. API keys provide programmatic access with role-based permissions
4. Personal API keys inherit permissions from user's role group
5. Bot API keys have extended permissions and can only be created by officers/developers
6. API keys must be rotated regularly for security
7. OAuth tokens must be refreshed before expiration
8. Failed authentication attempts are logged and rate-limited

### Character Transfer Rules:
1. **Discord user primacy**: All points, bids, and transactions are linked to Discord users, not characters
2. **Character name snapshots**: Transaction tables store character names as reference data only
3. **No hard character links**: Transaction tables have no foreign key constraints to character table
4. **Transfer flexibility**: Characters can be reassigned between Discord users without breaking transaction history
5. **Historical preservation**: Character names in transaction records remain unchanged after transfers
6. **Point continuity**: Discord user point balances are unaffected by character ownership changes
7. **Lookup methodology**: Character names are used to identify current Discord user ownership at transaction time

### Bidding Rules:
1. **Dynamic pricing**: Items have no fixed costs, all pricing determined by bidding
2. **Balance validation**: Users cannot bid more than their current DKP balance
3. **Single active session**: Only one bidding session per item per raid
4. **Minimum bid**: All bids must be positive (> 0 DKP)
5. **Session closure**: Bidding sessions must be explicitly closed to determine winner
6. **Automatic deduction**: Winning bid amount automatically deducted from user balance
7. **Bid history preservation**: All bids recorded for audit and analytics
8. **Discord bot integration**: Bidding controlled and processed via Discord bot
9. **Real-time validation**: API validates bids against current user balance
10. **Session timeouts**: Bidding sessions can have time limits

### Calculation Rules:
1. Current balance = Total Earned - Total Spent + Total Adjustments
2. Alt character points can optionally roll up to main character
3. Point adjustments require a reason and admin approval
4. Historical data must be preserved for audit purposes

### Discord Integration Rules:
1. System serves as authoritative source for Discord role assignments
2. Role changes trigger automatic Discord synchronization
3. Discord sync failures are logged and retried
4. Manual sync override available for administrators
5. **Discord roles are managed directly through User.role_group field, no character-level ranks**

### Recruitment Voting Rules:
1. **Voting options**: pass, fail, recycle (three options available)
2. **Vote acceptance**: Accept votes from ALL members regardless of attendance
3. **Vote counting**: Only count votes from members with ≥15% 30-day attendance
4. **Vote visibility tiers**:
   - **Guests/Applicants**: NO ACCESS to any voting data
   - **Members**: See only total vote counts (pass: X, fail: Y, recycle: Z)
   - **Developers**: Same access as members (total counts only)
   - **Recruiters/Officers**: See individual voter names and votes + attendance breakdown
5. **Vote participation**: Only members, developers, recruiters, and officers can vote
6. **Vote changes**: Voting users can change votes unlimited times during voting period
7. **Change tracking**: Record total number of vote changes per user
8. **Attendance snapshot**: Capture voter's attendance percentage at time of vote
9. **Decision calculation**: Final decision based only on counted votes (≥15% attendance)
10. **Breakdown reporting**: Show recruiters/officers total vs counted vote statistics
11. **Voting period**: Exactly 48 hours from start
11. **Applications require recruiter review and member voting**
12. **Two-stage process**: recruiter trial acceptance → member voting
13. **Trial periods have defined start and end dates**
14. **Discord webhook notifications for trial acceptance and voting periods**

## Views for Common Queries

### Character Point Balances View:
```sql
CREATE VIEW character_balances AS
SELECT 
    c.id as character_id,
    c.name as character_name,
    c.is_main,
    dp.id as dkp_pool_id,
    dp.name as pool_name,
    COALESCE(cps.current_balance, 0) as current_balance,
    COALESCE(cps.total_earned, 0) as total_earned,
    COALESCE(cps.total_spent, 0) as total_spent,
    COALESCE(cps.total_adjustments, 0) as total_adjustments
FROM characters c
CROSS JOIN dkp_pools dp
LEFT JOIN character_points_summary cps ON c.id = cps.character_id AND dp.id = cps.dkp_pool_id
WHERE c.is_active = TRUE AND dp.is_active = TRUE;
```

### Recent Activity View:
```sql
CREATE VIEW recent_activity AS
(
    SELECT 
        'attendance' as activity_type,
        ra.character_id,
        ra.dkp_pool_id,
        ra.points_earned as points_change,
        r.name as description,
        ra.created_at
    FROM raid_attendance ra
    JOIN raids r ON ra.raid_id = r.id
    WHERE ra.points_earned > 0
)
UNION ALL
(
    SELECT 
        'loot' as activity_type,
        ld.character_id,
        ld.dkp_pool_id,
        -ld.points_spent as points_change,
        i.name as description,
        ld.created_at
    FROM loot_distribution ld
    JOIN items i ON ld.item_id = i.id
)
UNION ALL
(
    SELECT 
        'adjustment' as activity_type,
        pa.character_id,
        pa.dkp_pool_id,
        pa.points_change,
        pa.reason as description,
        pa.created_at
    FROM point_adjustments pa
)
ORDER BY created_at DESC;
```

### Voting Eligible Members View:
```sql
CREATE VIEW voting_eligible_members AS
SELECT 
    u.id as user_id,
    u.username,
    u.discord_id,
    mas.attendance_percentage,
    mas.total_raids_30_days,
    mas.attended_raids_30_days,
    mas.is_voting_eligible,
    mas.last_updated
FROM users u
JOIN member_attendance_summary mas ON u.id = mas.user_id
WHERE u.is_active = TRUE 
    AND u.membership_status = 'member'
    AND mas.calculation_date = CURRENT_DATE
    AND mas.is_voting_eligible = TRUE;
```

### Member Vote Summary (Public View):
```sql
CREATE VIEW member_vote_summary AS
SELECT 
    ga.id as application_id,
    ga.character_name,
    ga.status,
    ga.voting_start_date,
    ga.voting_end_date,
    
    -- Total vote counts (what members see)
    COUNT(CASE WHEN av.vote = 'pass' THEN 1 END) as total_pass_votes,
    COUNT(CASE WHEN av.vote = 'fail' THEN 1 END) as total_fail_votes,
    COUNT(CASE WHEN av.vote = 'recycle' THEN 1 END) as total_recycle_votes,
    COUNT(av.id) as total_votes_cast,
    
    -- Voting status
    CASE 
        WHEN ga.voting_end_date < NOW() THEN 'expired'
        WHEN ga.voting_start_date > NOW() THEN 'not_started'
        ELSE 'active'
    END as voting_status
FROM guild_applications ga
LEFT JOIN application_votes av ON ga.id = av.application_id
WHERE ga.status IN ('voting_active', 'voting_complete')
GROUP BY ga.id, ga.character_name, ga.status, ga.voting_start_date, ga.voting_end_date;
```

### Recruiter/Officer Vote Summary (Detailed View):
```sql
CREATE VIEW officer_vote_summary AS
SELECT 
    ga.id as application_id,
    ga.character_name,
    ga.status,
    ga.voting_start_date,
    ga.voting_end_date,
    
    -- Total votes (all members)
    COUNT(CASE WHEN av.vote = 'pass' THEN 1 END) as total_pass_votes,
    COUNT(CASE WHEN av.vote = 'fail' THEN 1 END) as total_fail_votes,
    COUNT(CASE WHEN av.vote = 'recycle' THEN 1 END) as total_recycle_votes,
    COUNT(av.id) as total_votes_cast,
    
    -- Counted votes (≥15% attendance only)
    COUNT(CASE WHEN av.vote = 'pass' AND av.is_counted = TRUE THEN 1 END) as counted_pass_votes,
    COUNT(CASE WHEN av.vote = 'fail' AND av.is_counted = TRUE THEN 1 END) as counted_fail_votes,
    COUNT(CASE WHEN av.vote = 'recycle' AND av.is_counted = TRUE THEN 1 END) as counted_recycle_votes,
    COUNT(CASE WHEN av.is_counted = TRUE THEN 1 END) as counted_votes_total,
    
    -- Statistics
    COUNT(CASE WHEN av.is_counted = FALSE THEN 1 END) as excluded_votes,
    SUM(av.vote_changes) as total_vote_changes,
    COUNT(CASE WHEN av.vote_changes > 0 THEN 1 END) as voters_who_changed,
    
    -- Voting status
    CASE 
        WHEN ga.voting_end_date < NOW() THEN 'expired'
        WHEN ga.voting_start_date > NOW() THEN 'not_started'
        ELSE 'active'
    END as voting_status
FROM guild_applications ga
LEFT JOIN application_votes av ON ga.id = av.application_id
WHERE ga.status IN ('voting_active', 'voting_complete')
GROUP BY ga.id, ga.character_name, ga.status, ga.voting_start_date, ga.voting_end_date;
```

### Individual Vote Details (Recruiter/Officer Only):
```sql
CREATE VIEW individual_vote_details AS
SELECT 
    av.application_id,
    u.discord_username,
    u.role_group,
    av.vote,
    av.attendance_percentage,
    av.is_counted,
    av.vote_changes,
    av.comments,
    av.created_at,
    av.updated_at
FROM application_votes av
JOIN users u ON av.user_id = u.id
ORDER BY av.application_id, av.created_at;
```

## SQLAlchemy Event Listeners for Data Consistency

### Update User Points Summary:
```python
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(RaidAttendance, 'after_insert')
@event.listens_for(RaidAttendance, 'after_update')
@event.listens_for(RaidAttendance, 'after_delete')
def update_points_on_attendance_change(mapper, connection, target):
    """Update user points summary when attendance changes"""
    session = Session(bind=connection)
    try:
        summary = session.query(UserPointsSummary).filter_by(
            user_id=target.user_id,
            dkp_pool_id=target.dkp_pool_id
        ).first()
        
        if not summary:
            summary = UserPointsSummary(
                user_id=target.user_id,
                dkp_pool_id=target.dkp_pool_id
            )
            session.add(summary)
        
        # Recalculate totals
        summary.recalculate_totals(session)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

@event.listens_for(LootDistribution, 'after_insert')
@event.listens_for(LootDistribution, 'after_update') 
@event.listens_for(LootDistribution, 'after_delete')
def update_points_on_loot_change(mapper, connection, target):
    """Update user points summary when loot changes"""
    # Similar implementation to attendance change
    pass

@event.listens_for(PointAdjustment, 'after_insert')
@event.listens_for(PointAdjustment, 'after_update')
@event.listens_for(PointAdjustment, 'after_delete') 
def update_points_on_adjustment_change(mapper, connection, target):
    """Update user points summary when adjustments change"""
    # Similar implementation to attendance change
    pass
```

## SQLAlchemy Database Configuration

### Database Connection Setup:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/eq_dkp")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False  # Set to True for SQL query logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Database dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Models Module Structure:
```python
# models/__init__.py
from .base import Base
from .user import User, APIKey
from .character import Character, CharacterOwnershipHistory
from .dkp import DKPPool, UserPointsSummary, PointAdjustment
from .event import Event, Raid, RaidAttendance
from .item import Item, ItemBid, BidHistory, LootDistribution
from .application import GuildApplication, ApplicationVote, ApplicationComment
from .discord import DiscordSyncLog
from .analytics import MemberAttendanceSummary

__all__ = [
    "Base", "User", "APIKey", "Character", "CharacterOwnershipHistory",
    "DKPPool", "UserPointsSummary", "PointAdjustment", "Event", "Raid", 
    "RaidAttendance", "Item", "ItemBid", "BidHistory", "LootDistribution",
    "GuildApplication", "ApplicationVote", "ApplicationComment",
    "DiscordSyncLog", "MemberAttendanceSummary"
]
```

## Alembic Database Migrations

### Alembic Configuration:
```python
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://user:password@localhost/eq_dkp

[post_write_hooks]
hooks = black
black.type = console_scripts
black.entrypoint = black
black.options = -l 88

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### Migration Environment Setup:
```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add your model's MetaData object here
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import Base
target_metadata = Base.metadata

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment if available
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

# Interpret the config file for logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Sample Migration:
```python
# alembic/versions/001_initial_schema.py
"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create initial tables"""
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discord_id', sa.String(length=50), nullable=False),
        sa.Column('discord_username', sa.String(length=50), nullable=False),
        sa.Column('discord_discriminator', sa.String(length=10), nullable=True),
        sa.Column('discord_global_name', sa.String(length=50), nullable=True),
        sa.Column('discord_avatar', sa.String(length=255), nullable=True),
        sa.Column('discord_email', sa.String(length=255), nullable=True),
        sa.Column('role_group', sa.String(length=20), nullable=False),
        sa.Column('membership_status', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('discord_access_token', sa.Text(), nullable=True),
        sa.Column('discord_refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.CheckConstraint('LENGTH(discord_id) >= 10', name='users_discord_id_length'),
        sa.CheckConstraint('LENGTH(discord_username) >= 2', name='users_discord_username_length'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('discord_id')
    )
    op.create_index('idx_users_discord_id', 'users', ['discord_id'])
    op.create_index('idx_users_discord_username', 'users', ['discord_username'])
    op.create_index('idx_users_role_group', 'users', ['role_group'])
    
    # Additional tables would follow...

def downgrade() -> None:
    """Drop initial tables"""
    op.drop_table('users')
    # Additional drop statements would follow...
```

### Common Migration Commands:
```bash
# Initialize Alembic (only once)
alembic init alembic

# Generate new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Downgrade migration
alembic downgrade -1

# Show migration history
alembic history

# Show current revision
alembic current

# Generate SQL for migration (without applying)
alembic upgrade head --sql > migration.sql
```

## SQLAlchemy Query Optimization

### Using SQLAlchemy Core for Complex Queries:
```python
from sqlalchemy import text, func, and_, or_, case
from sqlalchemy.orm import joinedload, selectinload

# Complex user points query with eager loading
def get_user_points_with_details(db: Session, user_id: int):
    return db.query(User).options(
        selectinload(User.characters),
        joinedload(User.api_keys)
    ).filter(User.id == user_id).first()

# Efficient aggregation query
def get_dkp_leaderboard(db: Session, dkp_pool_id: int, limit: int = 50):
    return db.query(
        UserPointsSummary.user_id,
        User.discord_username,
        UserPointsSummary.current_balance,
        UserPointsSummary.total_earned,
        UserPointsSummary.total_spent
    ).join(User).filter(
        UserPointsSummary.dkp_pool_id == dkp_pool_id
    ).order_by(
        UserPointsSummary.current_balance.desc()
    ).limit(limit).all()

# Raw SQL for complex reporting
def get_attendance_report(db: Session, start_date, end_date):
    query = text("""
        SELECT 
            u.discord_username,
            COUNT(ra.id) as raids_attended,
            SUM(ra.points_earned) as total_points_earned
        FROM users u
        LEFT JOIN raid_attendance ra ON u.id = ra.user_id
        JOIN raids r ON ra.raid_id = r.id
        WHERE r.raid_date BETWEEN :start_date AND :end_date
        GROUP BY u.id, u.discord_username
        ORDER BY total_points_earned DESC
    """)
    return db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
```

## Performance Considerations

### SQLAlchemy Indexing Strategy:
```python
# Composite indexes for common query patterns
class RaidAttendance(Base):
    __tablename__ = "raid_attendance"
    
    # ... column definitions ...
    
    __table_args__ = (
        # Composite index for user + date range queries
        Index('idx_raid_attendance_user_date', 'user_id', 'raid_date'),
        # Composite index for raid + user queries
        Index('idx_raid_attendance_raid_user', 'raid_id', 'user_id'),
        # Partial index for active records only
        Index('idx_raid_attendance_active', 'is_active', postgresql_where=(is_active == True)),
    )

# Covering indexes for read-heavy queries
class UserPointsSummary(Base):
    __tablename__ = "user_points_summary"
    
    # ... column definitions ...
    
    __table_args__ = (
        # Covering index to avoid table lookups
        Index('idx_points_summary_covering', 
              'dkp_pool_id', 'current_balance', 'user_id',
              postgresql_include=['total_earned', 'total_spent']),
    )
```

### Query Optimization Best Practices:
1. **Use eager loading** for known relationships: `joinedload()`, `selectinload()`
2. **Implement query result caching** for frequently accessed data
3. **Use database connection pooling** with appropriate pool sizes
4. **Consider read replicas** for reporting and analytics queries
5. **Regular database maintenance**: VACUUM, ANALYZE, and statistics updates
6. **Monitor slow queries** and add appropriate indexes

### Scaling Considerations:
1. **Partition large tables** by date (raid_attendance, loot_distribution)
2. **Archive old data** beyond retention periods using Alembic migrations
3. **Use materialized views** for complex aggregations with scheduled refreshes
4. **Implement application-level caching** (Redis) for frequently accessed data
5. **Consider horizontal sharding** for extremely large datasets

## Development and Deployment

### Environment-Specific Configurations:
```python
# config.py
import os
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging" 
    PRODUCTION = "production"

class DatabaseConfig:
    def __init__(self):
        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
        
        if self.environment == Environment.PRODUCTION:
            self.database_url = os.getenv("DATABASE_URL")
            self.pool_size = 20
            self.echo = False
        elif self.environment == Environment.STAGING:
            self.database_url = os.getenv("STAGING_DATABASE_URL")
            self.pool_size = 10
            self.echo = False
        else:  # development
            self.database_url = "postgresql://user:password@localhost/eq_dkp_dev"
            self.pool_size = 5
            self.echo = True

db_config = DatabaseConfig()
```

### Testing Database Setup:
```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine("postgresql://test:test@localhost/eq_dkp_test")
    return engine

@pytest.fixture(scope="session")
def test_tables(test_engine):
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def test_db(test_engine, test_tables):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
```

This comprehensive SQLAlchemy and Alembic-based ERD provides a solid foundation for the FastAPI-based EQ DKP system while maintaining flexibility for future enhancements, ensuring data integrity, and supporting scalable development practices.