# Entity Relationship Diagram (ERD)
# EQ DKP FastAPI Database Design

## Database Schema Overview

This ERD defines the database structure for the FastAPI-based EQ DKP system, focusing on the core entities needed for guild roster management, DKP tracking, events, raids, and loot distribution.

## Core Entities

### 1. Users Table
**Purpose**: Store Discord user account information and OAuth data

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    discord_id VARCHAR(50) UNIQUE NOT NULL,  -- Primary external identifier
    discord_username VARCHAR(50) NOT NULL,
    discord_discriminator VARCHAR(10),  -- Legacy Discord discriminators
    discord_global_name VARCHAR(50),  -- New Discord display names
    discord_avatar VARCHAR(255),  -- Discord avatar hash/URL
    discord_email VARCHAR(255),  -- Email from Discord OAuth
    role_group VARCHAR(20) DEFAULT 'guest',  -- officer, recruiter, developer, member, applicant, guest
    membership_status VARCHAR(20) DEFAULT 'applicant',  -- member, trial, applicant, inactive
    is_active BOOLEAN DEFAULT TRUE,
    
    -- OAuth token storage
    discord_access_token TEXT,
    discord_refresh_token TEXT,
    token_expires_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    
    -- Constraints
    CONSTRAINT users_discord_id_length CHECK (LENGTH(discord_id) >= 10),
    CONSTRAINT users_discord_username_length CHECK (LENGTH(discord_username) >= 2),
    CONSTRAINT users_role_group_valid CHECK (role_group IN ('officer', 'recruiter', 'developer', 'member', 'applicant', 'guest')),
    CONSTRAINT users_membership_status_valid CHECK (membership_status IN ('member', 'trial', 'applicant', 'inactive'))
);

-- Indexes
CREATE UNIQUE INDEX idx_users_discord_id ON users(discord_id);
CREATE INDEX idx_users_discord_username ON users(discord_username);
CREATE INDEX idx_users_role_group ON users(role_group);
CREATE INDEX idx_users_membership_status ON users(membership_status);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_users_last_login ON users(last_login);
```

### 2. API Keys Table
**Purpose**: Store API keys for user and bot programmatic access

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,  -- User-defined name for the key
    key_hash VARCHAR(255) NOT NULL,  -- Hashed API key
    key_prefix VARCHAR(20) NOT NULL,  -- First few characters for identification
    key_type VARCHAR(20) DEFAULT 'personal',  -- personal, bot
    permissions TEXT[],  -- Array of permission scopes
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP NULL,
    usage_count INTEGER DEFAULT 0,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    expires_at TIMESTAMP NULL,  -- Optional expiration
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- For bot keys
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT api_keys_name_length CHECK (LENGTH(key_name) >= 3),
    CONSTRAINT api_keys_type_valid CHECK (key_type IN ('personal', 'bot')),
    CONSTRAINT api_keys_user_or_bot CHECK (
        (key_type = 'personal' AND user_id IS NOT NULL) OR 
        (key_type = 'bot' AND created_by IS NOT NULL)
    )
);

-- Indexes
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_type ON api_keys(key_type);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_created_by ON api_keys(created_by);
CREATE INDEX idx_api_keys_last_used ON api_keys(last_used_at);
```

### 3. Characters Table
**Purpose**: Store character information and link to users

```sql
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(50) UNIQUE NOT NULL,
    character_class VARCHAR(50),
    level INTEGER DEFAULT 1,
    rank_id INTEGER REFERENCES ranks(id) ON DELETE SET NULL,
    is_main BOOLEAN DEFAULT FALSE,
    main_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT characters_level_range CHECK (level >= 1 AND level <= 120),
    CONSTRAINT characters_name_length CHECK (LENGTH(name) >= 2),
    CONSTRAINT characters_main_not_self CHECK (main_character_id != id)
);

-- Indexes
CREATE INDEX idx_characters_name ON characters(name);
CREATE INDEX idx_characters_user_id ON characters(user_id);
CREATE INDEX idx_characters_main_id ON characters(main_character_id);
CREATE INDEX idx_characters_active ON characters(is_active);
CREATE INDEX idx_characters_rank ON characters(rank_id);
```

### 4. Ranks Table
**Purpose**: Define character ranks within the guild

```sql
CREATE TABLE ranks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT ranks_name_length CHECK (LENGTH(name) >= 2)
);

-- Indexes
CREATE INDEX idx_ranks_sort_order ON ranks(sort_order);
CREATE UNIQUE INDEX idx_ranks_default ON ranks(is_default) WHERE is_default = TRUE;
```

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
    description TEXT,
    item_class VARCHAR(50),  -- weapon, armor, misc, etc.
    rarity VARCHAR(20),      -- common, uncommon, rare, epic, legendary
    raid_tier VARCHAR(50),   -- raid difficulty/expansion tier
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT items_name_length CHECK (LENGTH(name) >= 2),
    CONSTRAINT items_rarity_valid CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary'))
);

-- Indexes
CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_class ON items(item_class);
CREATE INDEX idx_items_rarity ON items(rarity);
CREATE INDEX idx_items_raid_tier ON items(raid_tier);
CREATE INDEX idx_items_active ON items(is_active);
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

### 16. Discord Role Mappings Table
**Purpose**: Map guild ranks to Discord roles for automated synchronization

```sql
CREATE TABLE discord_role_mappings (
    id SERIAL PRIMARY KEY,
    rank_id INTEGER NOT NULL REFERENCES ranks(id) ON DELETE CASCADE,
    discord_role_id VARCHAR(50) NOT NULL,
    discord_role_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT discord_role_mappings_unique UNIQUE (rank_id, discord_role_id)
);

-- Indexes
CREATE INDEX idx_discord_mappings_rank ON discord_role_mappings(rank_id);
CREATE INDEX idx_discord_mappings_role ON discord_role_mappings(discord_role_id);
CREATE INDEX idx_discord_mappings_active ON discord_role_mappings(is_active);
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
**Purpose**: Track 30-day rolling attendance percentages for voting eligibility

```sql
CREATE TABLE member_attendance_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    calculation_date DATE NOT NULL,
    total_raids_30_days INTEGER NOT NULL DEFAULT 0,
    attended_raids_30_days INTEGER NOT NULL DEFAULT 0,
    attendance_percentage DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_30_days = 0 THEN 0.0
            ELSE ROUND((attended_raids_30_days::DECIMAL / total_raids_30_days::DECIMAL) * 100, 2)
        END
    ) STORED,
    is_voting_eligible BOOLEAN GENERATED ALWAYS AS (
        CASE 
            WHEN total_raids_30_days = 0 THEN FALSE
            ELSE ROUND((attended_raids_30_days::DECIMAL / total_raids_30_days::DECIMAL) * 100, 2) >= 15.0
        END
    ) STORED,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT attendance_summary_unique UNIQUE (user_id, calculation_date),
    CONSTRAINT attendance_raids_valid CHECK (attended_raids_30_days <= total_raids_30_days),
    CONSTRAINT attendance_counts_positive CHECK (total_raids_30_days >= 0 AND attended_raids_30_days >= 0)
);

-- Indexes
CREATE INDEX idx_attendance_summary_user ON member_attendance_summary(user_id);
CREATE INDEX idx_attendance_summary_character ON member_attendance_summary(character_id);
CREATE INDEX idx_attendance_summary_date ON member_attendance_summary(calculation_date);
CREATE INDEX idx_attendance_summary_eligible ON member_attendance_summary(is_voting_eligible);
CREATE INDEX idx_attendance_summary_percentage ON member_attendance_summary(attendance_percentage);
CREATE INDEX idx_attendance_summary_updated ON member_attendance_summary(last_updated);
```

## Relationship Summary

### One-to-Many Relationships:
1. **Users → Characters**: One user can have multiple characters
2. **Users → API Keys**: One user can have multiple personal API keys (for bot keys, via created_by)
3. **Characters → Characters**: One main character can have multiple alts
4. **Ranks → Characters**: One rank can be assigned to multiple characters
5. **Ranks → Discord Role Mappings**: One rank can map to multiple Discord roles
6. **Events → Raids**: One event type can have multiple raid instances
7. **Raids → Raid Attendance**: One raid can have multiple attendees
8. **Raids → Loot Distribution**: One raid can have multiple loot distributions
9. **Users → Raid Attendance**: One user can attend multiple raids (points awarded to user)
10. **Users → Loot Distribution**: One user can receive multiple items (points deducted from user)
11. **Users → Point Adjustments**: One user can have multiple adjustments
12. **Characters → Raid Attendance**: One character can attend multiple raids (for historical reference)
13. **Characters → Loot Distribution**: One character can receive multiple items (for historical reference)
14. **Characters → Character Ownership History**: One character can have multiple ownership transfers
15. **DKP Pools → Multiple Tables**: One pool can be referenced by attendance, loot, adjustments
16. **Users → Discord Sync Log**: One user can have multiple sync log entries
17. **Users → Guild Applications**: One recruiter can review multiple applications
18. **Guild Applications → Application Votes**: One application can have multiple votes
19. **Guild Applications → Application Comments**: One application can have multiple comments
20. **Users → Application Votes**: One member can vote on multiple applications
21. **Users → Application Comments**: One user can comment on multiple applications
22. **Users → Member Attendance Summary**: One user can have multiple attendance records
23. **Raids → Item Bids**: One raid can have multiple bidding sessions
24. **Item Bids → Bid History**: One bidding session can have multiple individual bids
25. **Users → Bid History**: One user can place bids in multiple sessions
26. **Users → Item Bids**: One user can win multiple bidding sessions

### Many-to-Many Relationships:
1. **Users ↔ Raids** (via Raid Attendance): Users can attend multiple raids via different characters, raids can have multiple users
2. **Users ↔ Items** (via Loot Distribution): Users can receive multiple items via different characters, items can go to multiple users
3. **Users ↔ Item Bids** (via Bid History): Users can bid on multiple items, items can receive bids from multiple users
4. **Members ↔ Applications** (via Application Votes): Eligible members can vote on multiple applications, applications can receive votes from multiple members
5. **Ranks ↔ Discord Roles** (via Discord Role Mappings): Ranks can map to multiple Discord roles, Discord roles can correspond to multiple ranks

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
26. Discord role mappings must reference valid ranks and roles
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
5. Discord role mappings can be many-to-many (rank to roles)

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

## Trigger Functions for Data Consistency

### Update Character Points Summary:
```sql
-- Function to update character points summary
CREATE OR REPLACE FUNCTION update_character_points()
RETURNS TRIGGER AS $$
BEGIN
    -- Update or insert character points summary
    INSERT INTO character_points_summary (character_id, dkp_pool_id, total_earned, total_spent, total_adjustments)
    VALUES (
        COALESCE(NEW.character_id, OLD.character_id),
        COALESCE(NEW.dkp_pool_id, OLD.dkp_pool_id),
        0, 0, 0
    )
    ON CONFLICT (character_id, dkp_pool_id) 
    DO UPDATE SET last_updated = CURRENT_TIMESTAMP;
    
    -- Recalculate totals (this would be more sophisticated in practice)
    -- This is a simplified version - actual implementation would be more efficient
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic updates
CREATE TRIGGER trigger_update_points_on_attendance
    AFTER INSERT OR UPDATE OR DELETE ON raid_attendance
    FOR EACH ROW EXECUTE FUNCTION update_character_points();

CREATE TRIGGER trigger_update_points_on_loot
    AFTER INSERT OR UPDATE OR DELETE ON loot_distribution
    FOR EACH ROW EXECUTE FUNCTION update_character_points();

CREATE TRIGGER trigger_update_points_on_adjustment
    AFTER INSERT OR UPDATE OR DELETE ON point_adjustments
    FOR EACH ROW EXECUTE FUNCTION update_character_points();
```

## Performance Considerations

### Indexing Strategy:
1. Primary keys and foreign keys are automatically indexed
2. Frequently queried columns (character names, dates) have dedicated indexes
3. Composite indexes for common query patterns
4. Partial indexes for boolean fields (e.g., active records only)

### Query Optimization:
1. Use materialized views for complex calculations
2. Implement proper connection pooling
3. Consider read replicas for reporting queries
4. Regular VACUUM and ANALYZE operations

### Scaling Considerations:
1. Partition large tables by date (raid_attendance, loot_distribution)
2. Archive old data beyond retention period
3. Use database connection pooling
4. Consider caching frequently accessed data

This ERD provides a solid foundation for the FastAPI-based EQ DKP system while maintaining flexibility for future enhancements and ensuring data integrity throughout the application lifecycle.