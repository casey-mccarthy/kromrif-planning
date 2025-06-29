# Product Requirements Document (PRD)
# EQ DKP Plus Django + DRF Migration

## 1. Executive Summary

This document outlines the requirements for migrating the existing EQ DKP Plus PHP application to a modern Django + Django REST Framework (DRF) based backend. The new system will serve as the **authoritative source of truth** for guild roster management, integrating with Discord bot services for automated role management. The system will include comprehensive character tracking, DKP point accrual, events/raids management, loot distribution tracking, and a recruitment application system for prospective guild members.

## 2. Project Overview

### 2.1 Current System Analysis
The existing EQ DKP Plus system is a comprehensive PHP-based application that manages:
- User accounts and authentication
- Guild member/character roster
- DKP point tracking with multiple pools
- Event and raid management
- Item distribution and point expenditure
- Complex point adjustment and calculation systems

### 2.2 Migration Scope
The Django + DRF migration will implement core functionality for:
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
**Fundamental Design**: Points are awarded to **Discord users** (not characters) to enable flexible character reassignment:
- Raid attendance data parsed by character names
- Points awarded to the Django User account owning that character
- Characters can be reassigned between users without point transfer complexity
- Simplified queries and reduced data complexity
- Support for extended player breaks with character transfers

## 3. Functional Requirements

### 3.1 User Management
**Priority: High**

#### 3.1.1 User Authentication
- **Django-allauth with Discord OAuth 2.0 as the primary authentication method**
- OAuth authorization code flow for web applications via django-allauth Discord provider
- Discord token management via django-allauth (automatic access token, refresh token handling)
- Session management using Django's built-in session framework + allauth integration
- **API Key System for programmatic access:**
  - Django REST Framework Token Authentication linked to allauth accounts
  - Personal API keys automatically generated from allauth Discord accounts
  - Bot API keys for Discord bots (admin-generated with extended permissions)
  - Scoped permissions based on Django groups and role_group field
  - Rate limiting per API key type via Django middleware

#### 3.1.2 User Profiles (Extended Django User Model)
- **Django's built-in User model extended with Discord data from django-allauth:**
  - Discord ID (unique identifier, populated from allauth SocialAccount)
  - Discord username and discriminator (from allauth extra_data)
  - Discord avatar URL (from allauth extra_data)
  - Discord email (from OAuth scope, stored in User.email)
- **Role Group System (single CharField with choices):**
  - officer, recruiter, developer, member, applicant, guest
  - Single role group per user (hierarchical permissions via Django groups)
- **API Key Management via DRF Token + allauth integration:**
  - Personal API keys automatically generated when Discord account is linked
  - DRF Token authentication linked to allauth SocialAccount
  - API key permissions based on Django groups + role_group
  - Usage tracking and rate limiting via custom middleware
- User preferences stored in Django User model or related profile model
- Account status management (Django's is_active field)
- Raid attendance tracking for voting eligibility

### 3.2 Character Management
**Priority: High**

#### 3.2.1 Character CRUD Operations
- Django Model with full CRUD via Django admin and DRF ViewSets
- Character name validation (unique=True constraint)
- Character-to-user association (ForeignKey to Django User)
- **Character reassignment between users** (for player breaks/transfers)
- Main character designation per user (BooleanField)
- Character ownership history tracking (separate model with foreign keys)

#### 3.2.2 Character Attributes
- Character name (CharField, required, unique)
- Character class and level (CharField and PositiveIntegerField)
- Character rank within guild (ForeignKey to Rank model, synchronized with Discord roles)
- Character status (Django's is_active field + custom status choices)
- Association with Django User account (ForeignKey)
- Main/Alt character relationship (self-referencing ForeignKey)
- Guild join date and rank history (auto_now_add timestamps + history model)
- Discord role synchronization metadata (separate DiscordRoleMapping model)

### 3.3 Guild Roster Management
**Priority: High**

#### 3.3.1 Roster Display
- Django ListView with filtering and pagination
- Filter by character class, rank, status via Django-filter
- Search functionality by character name (Django Q objects)
- Sort by various attributes (Django ordering)

#### 3.3.2 Character Relationships
- Track main character and alts via self-referencing ForeignKey
- Display character hierarchy via Django template tags
- Point inheritance rules between main/alt characters (business logic in models)

### 3.4 DKP Point System
**Priority: High**

#### 3.4.1 User-Based Point Tracking
- **Points awarded to Django Users, not characters**
- Current point totals per user per DKP pool (UserPointsSummary model)
- Point earning history (RaidAttendance model with character name snapshots)
- Point spending history (LootDistribution model with character attribution)
- Point adjustments (PointAdjustment model linked to users)

#### 3.4.2 Point Calculations
- Real-time point balance calculation per user (model properties + Django aggregation)
- Historical point tracking with character attribution (foreign keys to snapshots)
- Support for multiple DKP pools per user (separate DKPPool model)
- Point decay mechanisms (optional, via Django Celery tasks)
- **Simplified queries**: Django ORM handles user-based aggregation efficiently

#### 3.4.3 Character Reassignment Impact
- Character transfers don't require point migration (points stay with User)
- Historical records maintain character name for audit (CharField snapshots)
- Points remain with Django User account (ForeignKey relationships preserved)
- New character ownership immediately inherits user's point balance (automatic via User foreign keys)

### 3.5 Event Management
**Priority: High**

#### 3.5.1 Event Types
- Django Model with CRUD operations via admin and DRF
- Event point values (DecimalField with validators)
- Event descriptions and metadata (TextField)
- Event status (BooleanField is_active)

#### 3.5.2 Event Configuration
- Default point awards per event type (DecimalField)
- Event-specific item pools (ManyToManyField or through models)
- Event difficulty modifiers (DecimalField or IntegerField)

### 3.6 Raid Management
**Priority: High**

#### 3.6.1 Raid Creation
- Django Model with foreign key to Event
- Set raid date and time (DateTimeField)
- Assign raid leader (ForeignKey to User)
- Add raid notes/description (TextField)

#### 3.6.2 Raid Attendance
- **Parse character names from attendance data** (CharField snapshots)
- **Award points to Django User accounts** (ForeignKey to User)
- Track character attendance per raid for historical reference (CharField)
- Bulk attendance management via Django admin actions
- Late arrival/early departure tracking (CharField choices)
- Attendance-based point awards to users (automatic via Django signals)

### 3.7 Item and Bidding Management
**Priority: High**

#### 3.7.1 Item Database
- Django Model with standard fields
- Item name and description (CharField, TextField)
- Item categories/pools (CharField choices or ForeignKey to categories)
- Item rarity and metadata (CharField choices)
- **No fixed point costs** - all items awarded via bidding (no price field)
- Historical bidding data for reference pricing (BidHistory model)

#### 3.7.2 Dynamic Bidding System
- **In-game item drops trigger bidding periods** via Discord bot API calls
- Players bid up to their current DKP balance (validated in DRF serializers)
- **Discord bot parses game chat** for bid commands
- Real-time bid tracking and validation (Django models + DRF APIs)
- Bid closure and winner determination (Django model methods)
- **Discord bot submits final results** via DRF API endpoints:
  - Django User lookup by Discord ID
  - Item name (CharField)
  - Winning bid amount (DecimalField)
  - Character name context (CharField snapshot)

#### 3.7.3 Loot Distribution Processing
- **DRF API receives bid results from Discord bot**
- **Deduct winning bid amount from Django User balance** (UserPointsSummary updates)
- Record complete bidding history and final winner (BidHistory and LootDistribution models)
- Loot audit trail with bid progression (Django model relationships)
- Point expenditure validation against user balance (DRF serializer validation)

### 3.8 Point Adjustments
**Priority: Medium**

#### 3.8.1 Manual Adjustments
- **Admin ability to add/subtract points from Django User accounts** via Django admin
- Adjustment reasons and notes (CharField and TextField)
- Adjustment history and audit trail (PointAdjustment model with timestamps)
- Bulk adjustment capabilities (Django admin actions)
- **Character context recorded for reference** (CharField snapshot, no FK)

#### 3.8.2 Automated Adjustments
- Bonus point calculations (Django Celery tasks or management commands)
- Penalty applications (Django signals or manual admin actions)
- Attendance bonuses (automated via Django signals on RaidAttendance)
- Performance-based adjustments (custom Django management commands)

### 3.9 Discord Integration
**Priority: High**

#### 3.9.1 Authoritative Role Management
- System serves as single source of truth for guild roles (Django models)
- Automated Discord role synchronization via Discord bot API (DRF endpoints)
- Role hierarchy mapping (DiscordRoleMapping model linking Ranks to Discord roles)
- Member status change notifications to Discord (Django signals + webhook calls)
- Bulk role updates for rank changes (Django admin actions + batch API calls)

#### 3.9.2 Discord Bot Bidding Integration
- **Real-time DKP balance queries** for bid validation (DRF API endpoints)
- **Bid submission API** for Discord bot to submit results (DRF ViewSets)
- **Active bidding session tracking** for ongoing auctions (ItemBid model)
- **Bid validation endpoints** to prevent overbidding (DRF serializer validation)
- **Item award processing** with automatic point deduction (Django signals)
- **Bidding history tracking** for audit and analytics (BidHistory model)

#### 3.9.3 Discord Bot API Endpoints
- DRF API endpoints for current roster and role mappings
- Webhook notifications for member status changes (Django signals + requests)
- Authentication for Discord bot access via DRF Token Authentication
- Role assignment audit logging (DiscordSyncLog model)
- Error handling and retry mechanisms (Django-RQ or Celery)
- **Bidding system API access** with extended permissions (custom DRF permissions)

#### 3.9.4 Member Linking
- Discord ID association with Django User accounts (required field)
- Verification process for Discord-to-character linking (custom DRF endpoints)
- Automatic role assignment upon character approval (Django signals)
- Role removal upon character deactivation (Django signals)
- Conflict resolution for duplicate Discord IDs (unique constraint + validation)

### 3.10 Recruitment Application System
**Priority: High**

#### 3.10.1 Application Submission
- Django Form or DRF API endpoint for prospective members
- Required information collection (Django Model fields):
  - Character name and server (CharField fields)
  - Character class and level (CharField, PositiveIntegerField)
  - Previous guild experience (TextField)
  - Availability and time zone (TextField, CharField)
  - References from current members (TextField)
  - Discord username (CharField)
  - Application questionnaire responses (TextField)

#### 3.10.2 Application Management
- Django admin interface for recruiters
- Application status tracking (CharField choices: submitted, trial_accepted, rejected, voting_active, voting_complete)
- Initial recruiter review and screening (Django admin workflow)
- Comments and notes from recruiters (ApplicationComment model)
- Application history and archived records (Django soft delete or status tracking)
- Automated notifications to applicants (Django signals + email/Discord webhooks)

#### 3.10.3 Approval Workflow
- Two-stage approval process implemented in Django:
  1. **Recruiter Review**: Initial screening by recruiters (Django admin + permissions)
  2. **Member Voting**: Community vote by eligible members (custom DRF endpoints)
- Trial acceptance by recruiters (Django admin action + Discord webhook via signals)
- Member voting period (48 hours) initiated by recruiters (Django datetime fields)
- Voting eligibility: ≥15% raid attendance in last 30 days (MemberAttendanceSummary model)
- One vote per member (unique constraint on ApplicationVote model)
- Automatic character creation upon vote approval (Django signals)
- Trial member period management (Django datetime fields + Celery tasks)
- Promotion from trial to full member based on final vote results (Django admin actions)

#### 3.10.4 Trial Member Management
- Trial period duration tracking (Django datetime fields)
- Trial member performance monitoring (Django queries + reports)
- Trial member feedback collection (ApplicationComment model)
- Automatic promotion/removal at trial end (Django Celery tasks)
- Special trial member Discord roles (DiscordRoleMapping + Django signals)
- Limited access during trial period (Django groups + permissions)

#### 3.10.5 Voting System
- **Voting Options**: pass, fail, recycle (CharField choices in ApplicationVote model)
- **Vote Acceptance**: Accept votes from ALL members regardless of attendance (no restriction in DRF views)
- **Vote Counting**: Only count votes from members with ≥15% 30-day attendance (computed property on ApplicationVote)
- **Voting Period**: 48-hour window initiated by recruiters (Django datetime fields + validation)
- **Vote Modification**: Members can change votes unlimited times during active period (ApplicationVote update via DRF)
- **Change Tracking**: Record number of vote changes per user (PositiveIntegerField on ApplicationVote)
- **Access Control and Visibility Tiers** (Django permissions + DRF permissions):
  - **Guests/Applicants**: NO ACCESS to any voting data or participation (permission denied in DRF views)
  - **Members**: See only aggregate vote counts (limited DRF serializer fields)
  - **Developers**: Same access as members (same permission class)
  - **Recruiters/Officers**: See individual voter details, attendance breakdown, vote changes (full DRF serializer)
- **Decision Calculation**: Final decision based only on counted votes (Django model methods)
- **Attendance Snapshot**: Capture voter's attendance percentage at time of vote (DecimalField on ApplicationVote)
- **Discord Integration**: Application summary posted to webhook when trial accepted (Django signals)
- **Vote Results**: Automatic tallying and final decision execution (Django model methods + Celery tasks)
- **Notification System**: Discord notifications for voting start/end (Django signals + webhook calls)

## 4. Non-Functional Requirements

### 4.1 Performance
- API response times under 200ms for standard queries (Django query optimization + caching)
- Support for concurrent users (50+ simultaneous) (Django deployment configuration)
- Efficient database queries with proper indexing (Django Model Meta indexes)
- Caching for frequently accessed data (Django cache framework + Redis)

### 4.2 Security
- **Django-allauth with Discord OAuth 2.0** for web users
- **DRF Token Authentication linked to allauth** for programmatic access:
  - Personal API keys (DRF Token automatically created via allauth signals)
  - Bot API keys (custom APIKey model extending DRF Token with permissions)
  - Key rotation and expiration management (APIKey model fields + allauth token refresh)
- **Django Groups + role_group field** for role-based access control
- **Voting access restrictions** (Django permissions + DRF permission classes):
  - Guests/applicants: NO ACCESS via permission_classes
  - Members/Developers: Limited serializer fields
  - Recruiters/Officers: Full access via IsOfficerOrRecruiter permission
- Rate limiting per API key (Django middleware + django-ratelimit)
- Input validation and sanitization (Django forms + DRF serializers)
- SQL injection prevention via Django ORM (automatic parameterization)
- HTTPS enforcement for all endpoints (Django SECURE_SSL_REDIRECT)
- OAuth token secure storage and refresh handling (django-allauth automatic management)
- API key secure comparison via DRF Token authentication backend

### 4.3 Scalability
- Horizontal scaling capability (Django deployment with load balancer)
- Database connection pooling (Django database configuration)
- Stateless API design (DRF + Token authentication)
- Microservice-ready architecture (Django apps + API boundaries)

### 4.4 Reliability
- 99.5% uptime target (Django deployment configuration)
- Comprehensive error handling (Django exception handling + DRF error responses)
- Graceful degradation (Django try/except blocks + fallback responses)
- Automated backup systems (database backup + Django management commands)

## 5. API Design Requirements

### 5.1 Django REST Framework Architecture
- DRF ViewSets and Routers for consistent API structure
- Standard HTTP methods (GET, POST, PUT, DELETE) via DRF
- Consistent URL patterns via DRF routers
- Proper HTTP status codes via DRF Response
- JSON request/response format via DRF serializers

### 5.2 Core API Endpoints (Django URLs + DRF ViewSets)

#### 5.2.1 Authentication
```python
# Django-allauth URLs (django-allauth)
path('accounts/', include('allauth.urls')),  # Includes Discord OAuth flow
# This provides:
# /accounts/discord/login/ - Discord OAuth initiation
# /accounts/discord/login/callback/ - Discord OAuth callback
# /accounts/logout/ - Logout

# DRF Token Authentication (linked to allauth)
path('api/auth/token/', 'rest_framework.authtoken.views.obtain_auth_token')
path('api/auth/token/discord/', 'custom_views.discord_token_auth')  # Get token via Discord OAuth

# API Key Management (Custom DRF ViewSets linked to allauth)
path('api/auth/api-keys/', 'APIKeyViewSet.as_view({'get': 'list', 'post': 'create'})')
path('api/auth/api-keys/<uuid:pk>/', 'APIKeyViewSet.as_view({'delete': 'destroy'})')
path('api/auth/api-keys/<uuid:pk>/rotate/', 'APIKeyViewSet.as_view({'post': 'rotate'})')

# Administrative Bot Keys (admin only, custom permissions)
path('api/auth/bot-keys/', 'BotKeyViewSet.as_view({'get': 'list', 'post': 'create'})')
path('api/auth/bot-keys/<uuid:pk>/', 'BotKeyViewSet.as_view({'delete': 'destroy'})')
path('api/auth/bot-keys/<uuid:pk>/permissions/', 'BotKeyViewSet.as_view({'put': 'update_permissions'})')
```

#### 5.2.2 Users (Django User + DRF ViewSets)
```python
# DRF Generic Views + Custom ViewSets
path('api/users/me/', 'UserProfileView.as_view()')  # RetrieveUpdateAPIView
path('api/users/<int:pk>/', 'UserDetailView.as_view()')  # RetrieveAPIView
```

#### 5.2.3 Characters (Django Model + DRF ViewSet)
```python
# DRF ModelViewSet with custom actions
path('api/characters/', include(router.urls))  # Full CRUD via ViewSet
# Individual endpoints:
# GET|POST /api/characters/
# GET|PUT|DELETE /api/characters/{id}/
# POST /api/characters/{id}/reassign/
# GET /api/characters/{id}/ownership-history/
# GET /api/characters/by-name/{name}/
```

#### 5.2.4 Events (Django Model + DRF ViewSet)
```python
# Standard DRF ModelViewSet
path('api/events/', include(router.urls))
# GET|POST /api/events/
# GET|PUT|DELETE /api/events/{id}/
```

#### 5.2.5 Raids (Django Model + DRF ViewSet)
```python
# DRF ModelViewSet with nested resources
path('api/raids/', include(router.urls))
# Standard CRUD + custom actions:
# GET|POST /api/raids/
# GET|PUT|DELETE /api/raids/{id}/
# GET|POST /api/raids/{id}/attendance/
# GET|POST /api/raids/{id}/loot/
```

#### 5.2.6 Points (Custom DRF Views)
```python
# Custom DRF APIViews for point operations
path('api/points/user/<int:user_id>/', 'UserPointsView.as_view()')
path('api/points/user/<int:user_id>/pool/<int:dkp_pool_id>/', 'UserPoolPointsView.as_view()')
path('api/points/adjustments/', 'PointAdjustmentViewSet.as_view({'get': 'list', 'post': 'create'})')
path('api/points/history/user/<int:user_id>/', 'UserPointHistoryView.as_view()')
path('api/points/leaderboard/<int:dkp_pool_id>/', 'LeaderboardView.as_view()')
path('api/points/parse-attendance/', 'ParseAttendanceView.as_view()')
path('api/points/character-attribution/<str:character_name>/', 'CharacterAttributionView.as_view()')
```

#### 5.2.7 Items and Bidding (Django Models + DRF ViewSets)
```python
# Item Management (Standard DRF ModelViewSet)
path('api/items/', include(router.urls))
# GET|POST /api/items/
# GET|PUT|DELETE /api/items/{id}/
# GET /api/items/{id}/bid-history/

# Bidding System (Custom DRF Views for Discord Bot API)
path('api/bidding/start-bid/', 'StartBidView.as_view()')  # POST
path('api/bidding/active/', 'ActiveBidsView.as_view()')  # GET
path('api/bidding/place-bid/', 'PlaceBidView.as_view()')  # POST
path('api/bidding/close-bid/', 'CloseBidView.as_view()')  # POST
path('api/bidding/award-item/', 'AwardItemView.as_view()')  # POST
path('api/bidding/<str:bid_session_id>/', 'BidSessionDetailView.as_view()')  # GET
path('api/bidding/user/<str:discord_id>/max-bid/', 'UserMaxBidView.as_view()')  # GET
```

#### 5.2.8 Discord Integration (Custom DRF Views)
```python
# Discord Role Management (Custom DRF APIViews)
path('api/discord/roster/', 'DiscordRosterView.as_view()')  # GET
path('api/discord/roles/', 'DiscordRolesView.as_view()')  # GET
path('api/discord/members/<str:discord_id>/', 'DiscordMemberView.as_view()')  # GET
path('api/discord/sync-roles/', 'SyncRolesView.as_view()')  # POST
path('api/discord/link-member/', 'LinkMemberView.as_view()')  # POST
path('api/discord/unlink-member/<int:user_id>/', 'UnlinkMemberView.as_view()')  # DELETE
path('api/discord/audit-log/', 'DiscordAuditLogView.as_view()')  # GET
path('api/discord/webhooks/member-update/', 'MemberUpdateWebhookView.as_view()')  # POST

# Discord Bot Bidding Integration (Custom DRF APIViews)
path('api/discord/bid-results/', 'BidResultsView.as_view()')  # POST
path('api/discord/user/<str:discord_id>/balance/', 'UserBalanceView.as_view()')  # GET
path('api/discord/validate-bid/', 'ValidateBidView.as_view()')  # POST
path('api/discord/active-bids/', 'ActiveBidsView.as_view()')  # GET
```

#### 5.2.9 Recruitment Applications (Django Models + DRF ViewSets)
```python
# Application Management (DRF ModelViewSet with custom permissions)
path('api/applications/', include(router.urls))
# Standard CRUD + custom actions:
# GET|POST /api/applications/
# GET|PUT|DELETE /api/applications/{id}/
# POST /api/applications/{id}/trial-accept/
# POST /api/applications/{id}/reject/
# POST /api/applications/{id}/start-voting/
# GET /api/applications/pending/
# GET /api/applications/voting-active/
# GET /api/applications/trial-members/
# POST /api/applications/{id}/promote-trial/
# POST /api/applications/{id}/discord-webhook/

# Voting System (Custom DRF Views with Role-Based Access)
path('api/applications/<int:app_id>/vote/', 'ApplicationVoteView.as_view()')  # POST|PUT|DELETE
path('api/applications/<int:app_id>/votes/summary/', 'VoteSummaryView.as_view()')  # GET - all roles
path('api/applications/<int:app_id>/votes/member-view/', 'MemberVoteView.as_view()')  # GET - members+
path('api/applications/<int:app_id>/votes/officer-view/', 'OfficerVoteView.as_view()')  # GET - officers only
path('api/applications/<int:app_id>/votes/details/', 'VoteDetailsView.as_view()')  # GET - officers only  
path('api/applications/<int:app_id>/voting-eligibility/', 'VotingEligibilityView.as_view()')  # GET - officers only
path('api/applications/<int:app_id>/vote-changes/', 'VoteChangesView.as_view()')  # GET - officers only

# Note: Guests and applicants blocked via DRF permission classes
```

#### 5.2.10 Administrative (Django Admin + Custom DRF Views)
```python
# Administrative endpoints (Custom DRF APIViews with admin permissions)
path('api/admin/roster-audit/', 'RosterAuditView.as_view()')  # GET
path('api/admin/bulk-rank-update/', 'BulkRankUpdateView.as_view()')  # POST
path('api/admin/system-health/', 'SystemHealthView.as_view()')  # GET
path('api/admin/force-discord-sync/', 'ForceDiscordSyncView.as_view()')  # POST
path('api/admin/application-statistics/', 'ApplicationStatsView.as_view()')  # GET
```

### 5.3 API Documentation (Django + DRF)
- DRF Browsable API for interactive documentation
- Django REST Swagger or drf-spectacular for OpenAPI 3.0 specification
- Request/response examples via DRF metadata
- Authentication requirements per endpoint via DRF permission classes

## 6. Data Requirements

### 6.1 Data Migration
- Django management commands for data migration from existing MySQL database
- Django ORM for data validation and cleanup during migration
- Preserve historical records via Django models
- Maintain data relationships via Django foreign keys

### 6.2 Data Integrity
- Django Model constraints and validators for data validation
- Django database transactions for data consistency
- Django backup management commands
- Audit trail maintenance via Django model history (django-simple-history)

## 7. Integration Requirements

### 7.1 Database
- Django database configuration supporting PostgreSQL and MySQL
- Django database connection pooling configuration
- Django migrations for schema management
- Django Model Meta indexes for database optimization

### 7.2 External Services
- **Django-allauth** for Discord API integration and OAuth authentication
- **Discord Bot API** integration via requests library for role synchronization and webhooks
- Django logging framework for application logging
- Django management commands for backup services
- Django cache framework with Redis backend for caching layer

## 8. User Interface Requirements

### 8.1 API-First Design
- Complete functionality available via DRF APIs
- Django admin interface for administrative tasks
- JSON-based communication via DRF serializers
- Mobile-friendly API design via DRF

### 8.2 Frontend Integration Considerations
- React/Vue.js compatibility via DRF APIs
- Real-time updates capability via Django Channels (optional)
- CORS support via django-cors-headers
- Progressive Web App API support

## 9. Technical Constraints

### 9.1 Technology Stack
- Python 3.8+
- Django 4.2+ LTS framework
- Django REST Framework for API development
- Django-allauth for Discord OAuth integration
- PostgreSQL or MySQL database
- Redis for caching and session storage

### 9.2 Development Standards
- Type hints throughout codebase (Django-stubs for type checking)
- Comprehensive test coverage (80%+) via Django TestCase
- Code documentation via Django docstrings
- Code formatting (Black, isort) and linting (flake8, pylint)
- Django best practices (class-based views, proper model design)

## 10. Success Metrics

### 10.1 Performance Metrics
- API response time < 200ms (95th percentile) measured via Django debug toolbar
- Database query time < 50ms average via Django query optimization
- Memory usage optimization via Django performance monitoring
- CPU utilization targets via Django deployment monitoring

### 10.2 Functional Metrics
- 100% feature parity for core functionality vs existing system
- Zero data loss during Django migration
- User acceptance testing success via Django test suite
- API endpoint coverage via DRF test coverage reports

## 11. Timeline and Milestones

### Phase 1: Foundation (Weeks 1-2)
- Django project setup and configuration
- Django models and migrations creation
- Django-allauth for Discord OAuth setup
- Core User model extension and Character models

### Phase 2: Core DKP Features (Weeks 3-5)
- Character management via Django admin and DRF APIs
- Point tracking system via Django models and signals
- Event and raid management via DRF ViewSets
- Basic CRUD operations via Django ModelViewSets

### Phase 3: Discord Integration (Weeks 6-7)
- Discord bot API endpoints via custom DRF Views
- Role synchronization system via Django signals and Discord API
- Member linking functionality via Django User extension
- Webhook notifications via Django signals

### Phase 4: Recruitment System (Weeks 8-9)
- Application submission system via Django forms and DRF
- Approval workflow implementation via Django admin actions
- Trial member management via Django datetime fields
- Member voting system via custom DRF Views with permissions

### Phase 5: Advanced Features (Weeks 10-11)
- Point calculations and adjustments via Django model methods
- Loot tracking and distribution via Django signals
- Reporting and analytics via Django queries
- Performance optimization via Django caching

### Phase 6: Testing and Deployment (Weeks 12-13)
- Comprehensive Django test suite
- Discord bot integration testing via Django TestCase
- Data migration scripts via Django management commands
- Production deployment configuration
- Django admin documentation and user guides

## 12. Risk Assessment

### 12.1 Technical Risks
- Django migration complexity from PHP system
- Performance bottlenecks in Django ORM queries
- Django-allauth integration and customization challenges
- DRF API testing coverage gaps

### 12.2 Business Risks
- User adoption resistance to Django admin interface
- Feature gap identification during Django implementation
- Timeline delays due to Django learning curve
- Resource constraints for Django development

## 13. Acceptance Criteria

### 13.1 Functional Acceptance
- All core DRF APIs functional and tested via Django TestCase
- Data migration completed successfully via Django management commands
- Django-allauth and DRF Token authentication working
- Point calculations accurate via Django model validation

### 13.2 Performance Acceptance
- Response time targets met via Django optimization
- Concurrent user load handled via Django deployment configuration
- Database performance optimized via Django query optimization
- Memory and CPU usage within limits via Django monitoring

### 13.3 Quality Acceptance
- Django test coverage > 80% via coverage.py
- Security audit passed via Django security checklist
- Documentation complete via Django admin docs
- Code review standards met via Django coding standards

## 14. Django-Specific Implementation Details

### 14.1 Django Architecture Decisions
- **Extended Django User Model** instead of separate profile model for better allauth integration
- **Django-allauth** for Discord OAuth with automatic token management and refresh
- **Django Groups + role_group field** for hierarchical permission system
- **Django Signals** for automatic point summary updates and allauth data synchronization
- **DRF Token Authentication linked to allauth** for API access with automatic token generation
- **Custom allauth adapter** to populate User model from Discord OAuth data
- **Django Admin Actions** for bulk operations and administrative workflows
- **Django Management Commands** for data migration and maintenance tasks

### 14.2 Django Security Implementation
- **Django-allauth** for secure Discord OAuth 2.0 integration with automatic token refresh
- **DRF Permission Classes** for role-based API access control
- **Django Middleware** for rate limiting and API key authentication
- **Django Validators** for input validation and data integrity
- **Django CSRF Protection** for web interface security
- **Django Secret Key Management** for production security
- **Allauth Security Features** including automatic token validation and refresh

### 14.3 Django Performance Optimizations
- **Django Query Optimization** with select_related and prefetch_related
- **Django Caching Framework** with Redis backend for frequent queries
- **Django Database Indexes** via Model Meta for optimized lookups
- **Django Connection Pooling** for efficient database connections
- **Django Static File Handling** via WhiteNoise or CDN for production

### 14.4 Django Testing Strategy
- **Django TestCase** for model and view testing
- **DRF APITestCase** for API endpoint testing
- **Django TransactionTestCase** for testing database transactions
- **Django Mock** for external service integration testing
- **Django Fixtures or Factory Boy** for test data generation

This Django implementation maintains the same business logic and data relationships as the FastAPI version while leveraging Django's built-in features, django-allauth for Discord integration, admin interface, ORM capabilities, and the Django REST Framework for API development. The architecture takes advantage of Django's batteries-included philosophy and allauth's robust OAuth handling while maintaining the flexibility needed for Discord bot integration and complex guild management workflows.

## 15. Django-Allauth Integration Benefits

### 15.1 Automatic OAuth Management
- **Token Refresh**: Automatic handling of Discord OAuth token expiration and refresh
- **User Creation**: Automatic user account creation from Discord OAuth data
- **Data Synchronization**: Automatic population of User model fields from Discord API
- **Session Management**: Seamless integration with Django's session framework
- **Admin Interface**: Built-in admin interface for managing social accounts

### 15.2 Discord-Specific Features
- **Discord Provider**: Built-in Discord OAuth provider with proper scopes
- **Extra Data Storage**: Automatic storage of Discord user data (avatar, discriminator, etc.)
- **Account Linking**: Support for linking/unlinking Discord accounts to existing users
- **Signal Integration**: Rich signal system for custom business logic
- **Customization**: Extensive customization options via adapters and settings

### 15.3 Security Features
- **OAuth 2.0 Compliance**: Full OAuth 2.0 specification compliance
- **CSRF Protection**: Built-in CSRF protection for OAuth flows
- **State Validation**: Automatic state parameter validation
- **Token Security**: Secure token storage with encryption options
- **Rate Limiting**: Built-in rate limiting for OAuth endpoints

### 15.4 Development Benefits
- **Minimal Configuration**: Simple setup with sensible defaults
- **Extensive Documentation**: Well-documented with many examples
- **Active Maintenance**: Actively maintained with regular updates
- **Test Coverage**: High test coverage and reliability
- **Community Support**: Large community and ecosystem