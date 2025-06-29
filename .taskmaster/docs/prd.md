# Product Requirements Document (PRD)
# EQ DKP System Implementation

## 1. Executive Summary

This document outlines the requirements for implementing a modern EQ DKP (Dragon Kill Points) system to serve as the **authoritative source of truth** for guild roster management, integrating with Discord bot services for automated role management. The system will include comprehensive character tracking, DKP point accrual, events/raids management, loot distribution tracking, and a recruitment application system for prospective guild members.

**Key Design Decision**: Following the rank refactoring, characters do not have ranks, groups, or roles - only Discord users have role assignments through the `role_group` field.

## 2. Implementation Options

The system can be implemented using either:
- **Django + Django REST Framework (DRF)** - Full-featured web framework with admin interface
- **FastAPI + SQLAlchemy** - High-performance API-first approach with automatic documentation

Both implementations share the same core business logic and database schema, differing primarily in framework-specific features and development approach.

## 3. Core System Requirements

### 3.1 User Management
**Priority: High**

#### Discord OAuth Integration
- Primary authentication method using Discord OAuth 2.0
- No username/password login system
- All user accounts must be linked to Discord ID
- Support for Discord avatar, username, discriminator, and global name fields
- Automatic user creation from Discord OAuth data

#### Role-Based Access Control
- **Officer**: Full administrative access
- **Recruiter**: Member management, application review
- **Developer**: Technical access, API keys
- **Member**: Standard guild member access
- **Applicant**: Limited access during trial period
- **Guest**: Minimal read-only access

#### API Key Management
- Personal API keys for user programmatic access
- Bot API keys for Discord bot integration
- Role-based permission scoping
- Expiration dates and usage tracking
- Rate limiting per key

### 3.2 Character Management
**Priority: High**

#### Character Data Model
- **No character ranks**: Characters are simplified to focus on character data only
- Character name (unique across system)
- Character class and level
- Main/alt character relationships
- User ownership (can be transferred)
- Active/inactive status
- Optional notes field

#### Character Ownership
- Characters belong to Discord users
- Support for character transfers between users
- Ownership history tracking
- Point balances remain with Discord users during transfers

### 3.3 DKP Points System
**Priority: High**

#### User-Centric Point Management
- **Points belong to Discord users**, not characters
- Support for multiple DKP pools (Main Raid, Alt Raid, etc.)
- Real-time balance calculations
- Point adjustment system with audit trail
- Materialized views for performance

#### Transaction Types
- **Raid Attendance**: Points earned for participating in raids
- **Loot Distribution**: Points spent on items through bidding
- **Manual Adjustments**: Administrative point modifications
- All transactions maintain character name snapshots for historical reference

### 3.4 Raid and Event Management
**Priority: High**

#### Event Types
- Configurable event types (raids, meetings, etc.)
- Default point values per event type
- Active/inactive status

#### Raid Instances
- Specific instances of events with actual point awards
- Raid date and time tracking
- Notes and metadata
- Creator attribution

#### Attendance Tracking
- Character-based attendance (linked to Discord users)
- Multiple attendance statuses (present, late, early leave, absent)
- Points awarded to Discord user account
- 30/60/90 day and lifetime attendance metrics

### 3.5 Loot and Bidding System
**Priority: High**

#### Dynamic Item Pricing
- **No fixed item costs** - all pricing determined by bidding
- Real-time bid validation against user DKP balances
- Bidding session management
- Automatic winner determination

#### Bid Management
- Discord bot integration for bid collection
- Bid history tracking
- Balance validation at bid time
- Invalid bid handling

#### Loot Distribution
- Automatic point deduction from winners
- Item award tracking
- Character name snapshots for historical reference
- Discord integration for announcements

### 3.6 Recruitment System
**Priority: Medium**

#### Application Workflow
- Public application form
- Character information collection
- Multi-stage approval process:
  1. Initial submission
  2. Recruiter review
  3. Trial acceptance
  4. Member voting period (48 hours)
  5. Final approval/rejection

#### Voting System
- Attendance-based voting eligibility (≥15% 30-day attendance)
- Vote options: pass, fail, recycle
- Vote counting rules:
  - Accept votes from all eligible members
  - Count only votes from members with sufficient attendance
- Role-based vote visibility:
  - Members/Developers: See vote totals only
  - Recruiters/Officers: See individual votes and attendance breakdown

#### Application Comments
- Internal officer comments
- Applicant feedback system
- Comment visibility controls

### 3.7 Discord Integration
**Priority: High**

#### Role Synchronization
- **Direct user role management** (no character rank mapping)
- Automatic Discord role assignment based on User.role_group
- Sync failure logging and retry mechanisms
- Manual sync override capabilities

#### Bot Integration
- Raid attendance collection
- Bidding system integration
- Application notifications
- Role change announcements

### 3.8 Analytics and Reporting
**Priority: Medium**

#### Attendance Analytics
- Rolling 30/60/90 day attendance percentages
- Lifetime attendance tracking
- Voting eligibility calculations
- Performance trend analysis

#### DKP Analytics
- Point balance distributions
- Spending pattern analysis
- Earning trend tracking
- Pool balance monitoring

## 4. Technical Requirements

### 4.1 Database Design
- PostgreSQL as primary database
- User-centric data model with character ownership transfers
- Materialized views for performance optimization
- Comprehensive indexing strategy
- Data integrity constraints

### 4.2 API Design
- RESTful API endpoints
- Role-based access control
- Rate limiting and authentication
- Comprehensive error handling
- API documentation (OpenAPI/Swagger)

### 4.3 Performance Requirements
- Response times < 200ms for standard queries
- Support for 100+ concurrent users
- Efficient bulk operations
- Caching strategy for frequently accessed data

### 4.4 Security Requirements
- Discord OAuth 2.0 integration
- Secure API key management
- Input validation and sanitization
- SQL injection prevention
- Rate limiting and DDoS protection

## 5. Integration Requirements

### 5.1 Discord Bot Integration
- Webhook support for real-time updates
- Command handling for DKP queries
- Bidding system integration
- Role synchronization APIs

### 5.2 External Data Sources
- EverQuest log file parsing (future)
- Discord API integration
- Guild recruitment platforms (future)

## 6. Migration Considerations

### 6.1 Data Migration
- Existing DKP data import
- User account migration from legacy system
- Character ownership reconciliation
- Historical data preservation

### 6.2 System Transition
- Gradual rollout strategy
- Data validation and reconciliation
- Legacy system decommissioning
- User training and documentation

## 7. Success Criteria

### 7.1 Functional Success
- Complete feature parity with legacy system
- Successful Discord integration
- Zero data loss during migration
- User acceptance testing completion

### 7.2 Performance Success
- Sub-200ms API response times
- 99.9% uptime achievement
- Successful load testing with 100+ concurrent users
- Efficient database query performance

### 7.3 User Experience Success
- Intuitive user interface
- Seamless Discord authentication
- Responsive design across devices
- Comprehensive help documentation

## 8. Constraints and Assumptions

### 8.1 Technical Constraints
- Must integrate with existing Discord server
- PostgreSQL database requirement
- RESTful API architecture
- Modern web framework usage

### 8.2 Business Constraints
- Guild-specific customization requirements
- Existing user workflow preservation
- Discord-first authentication approach
- Character transfer support requirement

### 8.3 Assumptions
- Discord remains primary communication platform
- Guild members have Discord accounts
- EverQuest gameplay patterns remain consistent
- Guild size remains manageable (<200 active members)

## 9. Implementation Phases

### Phase 1: Core Foundation
- User authentication and management
- Basic character management
- Discord integration setup
- Database schema implementation

### Phase 2: DKP System
- Point tracking and management
- Raid and event management
- Attendance tracking
- Basic reporting

### Phase 3: Advanced Features
- Bidding system implementation
- Recruitment application workflow
- Advanced analytics
- Performance optimization

### Phase 4: Integration and Polish
- Discord bot feature completion
- Migration from legacy system
- User training and documentation
- Performance tuning and monitoring

## 10. Risk Mitigation

### 10.1 Technical Risks
- **Discord API changes**: Maintain abstraction layer for Discord integration
- **Performance bottlenecks**: Implement comprehensive caching and optimization
- **Data corruption**: Regular backups and transaction integrity checks
- **Security vulnerabilities**: Regular security audits and updates

### 10.2 Business Risks
- **User adoption resistance**: Gradual rollout with comprehensive training
- **Feature gaps**: Thorough requirements gathering and user feedback
- **Guild workflow disruption**: Parallel system operation during transition
- **Data migration issues**: Extensive testing and validation procedures

This PRD serves as the foundation for implementation planning and can be used with Task Master AI to generate detailed development tasks for either Django or FastAPI implementations.