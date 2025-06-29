# Product Requirements Document (PRD)
# EQ DKP Plus FastAPI Migration

## 1. Executive Summary

This document outlines the requirements for migrating the existing EQ DKP Plus PHP application to a modern FastAPI-based backend. The new system will serve as the **authoritative source of truth** for guild roster management, integrating with Discord bot services for automated role management. The system will include comprehensive character tracking, DKP point accrual, events/raids management, loot distribution tracking, and a recruitment application system for prospective guild members.

## 2. Project Overview

### 2.1 Current System Analysis
The existing EQ DKP Plus system is a comprehensive PHP-based application that manages:
- User accounts and authentication
- Guild member/character roster
- DKP point tracking with single pool system
- Event and raid management
- Item distribution and point expenditure
- Complex point adjustment and calculation systems

### 2.2 Migration Scope
The FastAPI migration will implement core functionality for:
- **Authoritative guild roster management** (primary source of truth)
- **Discord bot integration** for automated role synchronization
- **Recruitment application system** with approval workflows
- Character association with users
- Point accrual tracking
- Events (raid types) management
- Raids (instances of events with point awards)
- Item drops and point expenditures

### 2.3 System Authority and Integration
This system will serve as the **single source of truth** for:
- Guild membership status and roles
- Character roster and rank assignments
- Member status changes (promotions, demotions, removals)
- Discord role synchronization data

### 2.4 Point Allocation Architecture
**Fundamental Design**: Points are awarded to **Discord users** (not characters) with a single DKP pool system to enable flexible character reassignment:
- Single DKP pool for all guild activities (no multiple pools)
- Raid attendance data parsed by character names
- Points awarded to the Discord user account owning that character
- Characters can be reassigned between users without point transfer complexity
- Simplified queries and reduced data complexity
- Support for extended player breaks with character transfers

## 3. Functional Requirements

### 3.1 User Management
**Priority: High**

#### 3.1.1 User Authentication
- **Discord OAuth 2.0 as the sole authentication method**
- OAuth authorization code flow for web applications
- Discord token management (access tokens, refresh tokens)
- Session management via Discord OAuth tokens
- **API Key System for programmatic access:**
  - Personal API keys for users (self-generated)
  - Bot API keys for Discord bots (admin-generated)
  - Scoped permissions based on user role groups
  - Rate limiting per API key type

#### 3.1.2 User Profiles
- **Discord user data as primary identity:**
  - Discord ID (unique identifier)
  - Discord username and discriminator
  - Discord avatar URL
  - Discord email (from OAuth scope)
- **Role Group System (replaces individual role flags):**
  - developer, officer, recruiter, member, applicant, guest (in order of highest to lowest permissions)
  - Single role group per user (hierarchical permissions)
- **API Key Management:**
  - Personal API key generation and rotation
  - API key permissions based on role group
  - Usage tracking and rate limiting
- User preferences and application settings
- Account status management (active/inactive)
- Raid attendance tracking for voting eligibility

### 3.2 Character Management
**Priority: High**

#### 3.2.1 Character CRUD Operations
- Create, read, update, delete characters
- Character name validation (unique within guild)
- Character-to-user association (one user can have multiple characters)
- **Character reassignment between users** (for player breaks/transfers)
- Main character designation per user
- Character ownership history tracking

#### 3.2.2 Character Attributes
- Character name (required, unique)
- Character class and level
- Character rank within guild
- Character status (active/inactive/applicant)
- Association with user account
- Main/Alt character relationship
- Guild join date and rank history
- **Note**: Discord roles are static and managed externally (no Discord role models needed)

### 3.3 Guild Roster Management
**Priority: High**

#### 3.3.1 Roster Display
- List all active guild members
- Filter by character class, rank, status
- Search functionality by character name
- Sort by various attributes (name, class, rank, points)

#### 3.3.2 Character Relationships
- Track main character and alts
- Display character hierarchy
- Point inheritance rules between main/alt characters

### 3.4 DKP Point System
**Priority: High**

#### 3.4.1 User-Based Point Tracking
- **Points awarded to Discord users, not characters**
- **Single DKP pool system** (no multiple pools)
- Current point totals per user
- Point earning history via multiple sources:
  - Raid attendance (character name recorded for reference)
  - Bonus assignments (manual additions with bonus type)
  - Guild task completion (track targets, farm items, level characters, etc.)
- Point spending/loss history:
  - Item purchases (item purchased by which character)
  - Officer punishments (manual deductions with penalty type)

#### 3.4.2 Point Calculations
- Real-time point balance calculation per user
- Historical point tracking with character attribution
- **Single DKP pool system** (simplified model without multiple pools)
- Point decay mechanisms (optional)
- **Simplified queries**: User-based aggregation with single pool system

#### 3.4.3 Character Reassignment Impact
- Character transfers don't require point migration
- Historical records maintain character name for audit
- Points remain with Discord user account
- New character ownership immediately inherits user's point balance

### 3.5 Event Management
**Priority: High**

#### 3.5.1 Event Types
- Create and manage raid/event types
- Event point values
- Event descriptions and metadata
- Event status (active/inactive)

#### 3.5.2 Event Configuration
- Default point awards per event type
- Event difficulty modifiers

### 3.6 Raid Management
**Priority: High**

#### 3.6.1 Raid Creation
- Create raid instances from event types
- Set raid date and time
- Assign raid leader
- Add raid notes/description

#### 3.6.2 Raid Attendance
- **Parse character names from attendance data**
- **Award points to Discord user accounts (character owners)**
- Track character attendance per raid for historical reference
- Bulk attendance management
- Late arrival/early departure tracking
- Attendance-based point awards to users
- **Multi-period attendance tracking**: Calculate and maintain 30/60/90 day rolling averages and lifetime statistics
- **Performance monitoring**: Display member consistency and participation trends across different time periods
- **Automated attendance calculations**: Background tasks to update rolling averages for all active members

### 3.7 Item and Loot Management
**Priority: High**

#### 3.7.1 Item Database
- Item name only
- Simplified item tracking without categories or metadata
- Item names for loot distribution tracking (simplified model)

#### 3.7.2 Loot Distribution System
- **Loot distribution decisions made in-game by guild leadership**
- **Discord bot submits final loot awards** via API:
  - Discord user ID
  - Item name
  - Points spent for item
  - Character name context
  - Raid context

#### 3.7.3 Loot Distribution Processing
- **API receives loot awards from Discord bot**
- **Deduct point cost from Discord user balance**
- Record loot awards and final recipient
- Loot audit trail with award history
- Point expenditure validation against user balance

### 3.8 Point Adjustments
**Priority: Medium**

#### 3.8.1 Manual Adjustments
- **Officer/Admin ability to add/subtract points from user accounts**
- **Point earning methods**:
  - Raid attendance (automatic via attendance tracking)
  - Bonus assignments (manual additions with bonus type)
  - Guild task completion (manual additions: track targets, farm items, level characters, etc.)
- **Point loss methods**:
  - Item purchases (automatic via loot distribution)
  - Officer punishments (manual deductions with penalty type)
- Adjustment reasons and notes
- Adjustment history and audit trail
- Bulk adjustment capabilities
- **Character context recorded for reference (if applicable)**

#### 3.8.2 Automated Adjustments
- Bonus point calculations
- Penalty applications
- Attendance bonuses
- Performance-based adjustments

### 3.9 Discord Integration
**Priority: High**

#### 3.9.1 Member Status Management
- System serves as single source of truth for guild member status
- Member status change notifications to Discord
- **Discord roles are static and managed externally** (no role synchronization needed)
- Member linking and unlinking (User to Discord ID association)
- Bulk member status updates

#### 3.9.2 Discord Bot Loot Integration
- **Real-time DKP balance queries** for loot award validation
- **Loot award API** for Discord bot to submit results
- **Point validation endpoints** to prevent overspending
- **Item award processing** with automatic point deduction
- **Loot distribution tracking** for audit and analytics

#### 3.9.3 Discord Bot API Endpoints
- GET endpoints for current roster and member status
- Webhook notifications for member status changes
- Authentication for Discord bot access via bot API keys
- Member status change audit logging
- Error handling and retry mechanisms
- **Loot distribution API access** with extended permissions

#### 3.9.4 Member Linking
- Discord ID association with user accounts
- Verification process for Discord-to-character linking
- Member status updates upon character approval
- Member status updates upon character deactivation
- Conflict resolution for duplicate Discord IDs

### 3.10 Recruitment Application System
**Priority: High**

#### 3.10.1 Application Submission
- Public application form for prospective members
- Required information collection:
  - Character name and server
  - Character class and level
  - Previous guild experience
  - Availability and time zone
  - References from current members
  - Discord username
  - Application questionnaire responses

#### 3.10.2 Application Management
- Recruiter dashboard for reviewing applications
- Application status tracking (submitted, trial_accepted, rejected, voting_active, voting_complete)
- Initial recruiter review and screening
- Comments and notes from recruiters
- Application history and archived records
- Automated notifications to applicants

#### 3.10.3 Approval Workflow
- Two-stage approval process:
  1. **Recruiter Review**: Initial screening by recruiters
  2. **Member Voting**: Community vote by eligible members
- Trial acceptance by recruiters (immediate Discord webhook notification)
- Member voting period (48 hours) initiated by recruiters
- Voting eligibility: ≥15% raid attendance in last 30 days
- Attendance tracking: 30/60/90 day rolling averages and lifetime statistics for performance monitoring
- One vote per member (changeable during voting period)
- Automatic character creation upon vote approval
- Trial member period management
- Promotion from trial to full member based on final vote results

#### 3.10.4 Trial Member Management
- Trial period duration tracking
- Trial member performance monitoring
- Trial member feedback collection
- Automatic promotion/removal at trial end based on member vote results
- Special trial member Discord roles
- Limited access during trial period

#### 3.10.5 Voting System
- **Voting Options**: pass, fail, recycle (three choices available)
- **Vote Acceptance**: Accept votes from ALL members regardless of attendance
- **Vote Counting**: Only count votes from members with ≥15% 30-day attendance
- **Voting Period**: 48-hour window initiated by recruiters
- **Vote Modification**: Members can change votes unlimited times during active period
- **Change Tracking**: Record number of vote changes per user
- **Access Control and Visibility Tiers**:
  - **Guests/Applicants**: NO ACCESS to any voting data or participation
  - **Members**: See only aggregate vote counts (pass: X, fail: Y, recycle: Z)
  - **Recruiters**: See individual voter details, attendance breakdown, vote changes
  - **Officers/Developers**: Full administrative access to all voting data and controls
- **Decision Calculation**: Final decision based only on counted votes (≥15% attendance)
- **Attendance Snapshot**: Capture voter's attendance percentage at time of vote
- **Discord Integration**: Application summary posted to webhook when trial accepted
- **Vote Results**: Automatic tallying and final decision execution based on counted votes
- **Notification System**: Discord notifications for voting start/end

## 4. Non-Functional Requirements

### 4.1 Performance
- API response times under 200ms for standard queries
- Support for concurrent users (50+ simultaneous)
- Efficient database queries with proper indexing
- Caching for frequently accessed data

### 4.2 Security
- **Discord OAuth 2.0 authentication** for web users
- **API Key authentication** for programmatic access:
  - Personal API keys (user-scoped permissions)
  - Bot API keys (admin-generated, extended permissions)
  - Key rotation and expiration management
- **Role-based access control** via group system (officer, recruiter, developer, member, applicant, guest)
- **Voting access restrictions**:
  - Guests and applicants: NO ACCESS to voting data or participation
  - Members/Developers: Aggregate vote counts only
  - Recruiters/Officers: Full access to individual votes and statistics
- Rate limiting per API key and endpoint type
- Input validation and sanitization
- SQL injection prevention via parameterized queries
- HTTPS enforcement for all endpoints
- OAuth token secure storage and refresh handling
- API key hashing and secure comparison

### 4.3 Scalability
- Horizontal scaling capability
- Database connection pooling
- Stateless API design
- Microservice-ready architecture

### 4.4 Reliability
- 99.5% uptime target
- Comprehensive error handling
- Graceful degradation
- Automated backup systems

## 5. API Design Requirements

### 5.1 RESTful Architecture
- Standard HTTP methods (GET, POST, PUT, DELETE)
- Consistent URL patterns
- Proper HTTP status codes
- JSON request/response format

### 5.2 Core API Endpoints

#### 5.2.1 Authentication
```
# Discord OAuth Flow
GET /auth/discord/login
GET /auth/discord/callback
POST /auth/discord/refresh
POST /auth/logout

# API Key Management
GET /auth/api-keys
POST /auth/api-keys
DELETE /auth/api-keys/{key_id}
PUT /auth/api-keys/{key_id}/rotate

# Administrative Bot Keys (admin only)
GET /auth/bot-keys
POST /auth/bot-keys
DELETE /auth/bot-keys/{key_id}
PUT /auth/bot-keys/{key_id}/permissions
```

#### 5.2.2 Users
```
GET /users/me
PUT /users/me
GET /users/{user_id}
```

#### 5.2.3 Characters
```
GET /characters
POST /characters
GET /characters/{character_id}
PUT /characters/{character_id}
DELETE /characters/{character_id}
POST /characters/{character_id}/reassign
GET /characters/{character_id}/ownership-history
GET /characters/by-name/{character_name}
```

#### 5.2.4 Events
```
GET /events
POST /events
GET /events/{event_id}
PUT /events/{event_id}
DELETE /events/{event_id}
```

#### 5.2.5 Raids
```
GET /raids
POST /raids
GET /raids/{raid_id}
PUT /raids/{raid_id}
DELETE /raids/{raid_id}
GET /raids/{raid_id}/attendance
POST /raids/{raid_id}/attendance
GET /raids/{raid_id}/loot
POST /raids/{raid_id}/loot
```

#### 5.2.6 Points
```
GET /points/user/{user_id}
POST /points/adjustments
GET /points/history/user/{user_id}
GET /points/leaderboard
POST /points/parse-attendance
GET /points/character-attribution/{character_name}
GET /attendance/user/{user_id}/summary
GET /attendance/user/{user_id}/30-day
GET /attendance/user/{user_id}/60-day
GET /attendance/user/{user_id}/90-day
GET /attendance/user/{user_id}/lifetime
GET /attendance/leaderboard/30-day
GET /attendance/leaderboard/60-day
GET /attendance/leaderboard/90-day
GET /attendance/leaderboard/lifetime
```

#### 5.2.7 Items and Loot Distribution
```
# Item Management
GET /items
POST /items
GET /items/{item_id}
PUT /items/{item_id}
DELETE /items/{item_id}
GET /items/{item_id}/distribution-history

# Loot Distribution System (Discord Bot API)
POST /loot/award-item
GET /loot/user/{discord_id}/balance
GET /loot/distribution-history
```

#### 5.2.8 Discord Integration
```
# Discord Member Management
GET /discord/roster
GET /discord/members/{discord_id}
POST /discord/link-member
DELETE /discord/unlink-member/{user_id}
GET /discord/audit-log
POST /discord/webhooks/member-update

# Discord Bot Loot Integration
POST /discord/loot-award
GET /discord/user/{discord_id}/balance
POST /discord/validate-points
```

#### 5.2.9 Recruitment Applications
```
# Application Management
GET /applications
POST /applications
GET /applications/{application_id}
PUT /applications/{application_id}
DELETE /applications/{application_id}
POST /applications/{application_id}/trial-accept
POST /applications/{application_id}/reject
POST /applications/{application_id}/start-voting
GET /applications/pending
GET /applications/voting-active
GET /applications/trial-members
POST /applications/{application_id}/promote-trial
POST /applications/{application_id}/discord-webhook

# Voting System (Role-Based Access)
POST /applications/{application_id}/vote  # member, developer, recruiter, officer only
PUT /applications/{application_id}/vote   # member, developer, recruiter, officer only
DELETE /applications/{application_id}/vote # member, developer, recruiter, officer only
GET /applications/{application_id}/votes/summary      # member, developer, recruiter, officer only
GET /applications/{application_id}/votes/member-view  # member, developer, recruiter, officer only
GET /applications/{application_id}/votes/officer-view # recruiter, officer, developer only
GET /applications/{application_id}/votes/details      # recruiter, officer, developer only
GET /applications/{application_id}/voting-eligibility # recruiter, officer, developer only
GET /applications/{application_id}/vote-changes       # recruiter, officer, developer only

# Note: Guests and applicants have NO ACCESS to any voting endpoints
```

#### 5.2.10 Administrative
```
GET /admin/roster-audit
POST /admin/bulk-rank-update
GET /admin/system-health
POST /admin/force-discord-sync
GET /admin/application-statistics
```

### 5.3 API Documentation
- OpenAPI 3.0 specification
- Interactive Swagger UI
- Request/response examples
- Authentication requirements per endpoint

## 6. Data Requirements

### 6.1 Data Migration
- **Alembic migration scripts** from existing MySQL database to new SQLAlchemy models
- **Data validation and cleanup** using Pydantic models during migration
- **Preserve historical records** with proper foreign key relationships in SQLAlchemy
- **Maintain data relationships** through SQLAlchemy ORM relationships and constraints

### 6.2 Data Integrity
- **SQLAlchemy foreign key constraints** and relationship integrity
- **Pydantic data validation** rules for API inputs and outputs
- **Database-level constraints** defined in SQLAlchemy models
- **SQLAlchemy event listeners** for audit trail maintenance
- **Alembic-managed backup and recovery** procedures

## 7. Integration Requirements

### 7.1 Database
- **SQLAlchemy ORM** for database models and queries with proper relationships
- **Alembic** for automated database migrations and schema versioning
- **PostgreSQL** as primary database (MySQL support via SQLAlchemy dialects)
- **Connection pooling** with configurable pool sizes and connection recycling
- **Database indexing strategy** defined via SQLAlchemy `__table_args__`
- **Environment-specific configurations** for development, staging, and production

### 7.2 External Services
- **Discord API integration** for OAuth authentication and user data
- **Discord Bot API** for role synchronization and webhooks
- Logging and monitoring
- Backup services
- Caching layer (Redis) for Discord user data and API responses

## 8. User Interface Requirements

### 8.1 API-First Design
- Complete functionality available via API
- No server-side rendering
- JSON-based communication
- Mobile-friendly API design

### 8.2 Future Frontend Considerations
- React/Vue.js compatibility
- Real-time updates capability
- Responsive design support
- Progressive Web App features

## 9. Technical Constraints

### 9.1 Technology Stack
- **Python 3.8+** with type hints throughout
- **FastAPI framework** for API development
- **SQLAlchemy 2.0+** ORM for database models and queries
- **Alembic** for database migrations and schema management
- **Pydantic v2** for data validation and serialization
- **PostgreSQL** as primary database (with MySQL support via SQLAlchemy)

### 9.2 Development Standards
- Type hints throughout codebase
- Comprehensive test coverage (80%+)
- Code documentation
- Linting and formatting (Black, isort)

## 10. Success Metrics

### 10.1 Performance Metrics
- API response time < 200ms (95th percentile)
- Database query time < 50ms average
- Memory usage optimization
- CPU utilization targets

### 10.2 Functional Metrics
- 100% feature parity for core functionality
- Zero data loss during migration
- User acceptance testing success
- API endpoint coverage

## 11. Timeline and Milestones

### Phase 1: Foundation (Weeks 1-2)
- Project setup and configuration
- Database models and migrations
- Basic authentication system
- Core user and character models

### Phase 2: Core DKP Features (Weeks 3-5)
- Character management APIs
- Point tracking system
- Event and raid management
- Basic CRUD operations

### Phase 3: Discord Integration (Weeks 6-7)
- Discord bot API endpoints
- Role synchronization system
- Member linking functionality
- Webhook notifications

### Phase 4: Recruitment System (Weeks 8-9)
- Application submission system
- Approval workflow implementation
- Trial member management
- Officer voting system

### Phase 5: Advanced Features (Weeks 10-11)
- Point calculations and adjustments
- Loot tracking and distribution
- Reporting and analytics
- Performance optimization

### Phase 6: Testing and Deployment (Weeks 12-13)
- Comprehensive testing
- Discord bot integration testing
- Data migration scripts
- Production deployment
- Documentation finalization

## 12. Risk Assessment

### 12.1 Technical Risks
- Data migration complexity
- Performance bottlenecks
- Integration challenges
- Testing coverage gaps

### 12.2 Business Risks
- User adoption resistance
- Feature gap identification
- Timeline delays
- Resource constraints

## 13. Acceptance Criteria

### 13.1 Functional Acceptance
- All core APIs functional and tested
- Data migration completed successfully
- Authentication and authorization working
- Point calculations accurate

### 13.2 Performance Acceptance
- Response time targets met
- Concurrent user load handled
- Database performance optimized
- Memory and CPU usage within limits

### 13.3 Quality Acceptance
- Test coverage > 80%
- Security audit passed
- Documentation complete
- Code review standards met