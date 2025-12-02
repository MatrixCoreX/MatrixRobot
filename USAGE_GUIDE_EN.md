# MatrixCore Bot Usage Guide

## Table of Contents
- [User Commands](#user-commands)
  - [Private Chat Commands](#private-chat-commands)
  - [Group Commands](#group-commands)
- [Admin Commands](#admin-commands)
- [Feature Descriptions](#feature-descriptions)
- [Configuration Guide](#configuration-guide)

---

## User Commands

### Private Chat Commands

The following commands can only be used in private chat. Using them in a group will prompt "This command can only be used in private chat. Please contact the bot directly."

#### 1. `/start` - Register Bot and Get Invite Link

**Purpose**: Register an account when first using the bot and get your exclusive invite link

**Usage**:
```
/start
```

**Features**:
- Create user account (if not exists)
- If accessed via invite link, automatically record invitation relationship
- Display welcome message and exclusive invite link
- Invite link format: `https://t.me/{bot_username}?start={your_telegram_id}`

**Use Cases**:
- New users first time using the bot
- Need to get your own invite link for promotion

---

#### 2. `/me` - View Personal Information

**Purpose**: View your points, binding information, invite count, and other detailed information

**Usage**:
```
/me
```

**Displayed Content**:
- Telegram ID
- Current Points (Total Points)
- Unlocked Points (Points available for transfer)
- Monthly Earned Points
- Binance UID (if bound)
- X/Twitter Account (if bound)
- Community Account Address (if bound, displayed based on configuration)
- Successful Invite Count
- Exclusive Invite Link

**Use Cases**:
- Check current points status
- Verify binding information is correct
- View invite statistics

---

#### 3. `/bind` - Bind Account (Interactive)

**Purpose**: Select account type to bind via buttons

**Usage**:
```
/bind
```

**Features**:
- Display binding option buttons:
  - 🔗 Bind Binance UID
  - 🧵 Bind X Account
  - 🅰️ Bind Community Account (if `COMMUNITY_ACCOUNT_NAME` is configured)
- Click button to see specific binding command format

**Use Cases**:
- When unsure of binding command format
- When need to bind multiple accounts

---

#### 4. `/bind_binance <UID>` - Bind Binance UID

**Purpose**: Bind Binance account UID

**Usage**:
```
/bind_binance 12345678
```

**Parameters**:
- `<UID>`: Binance UID, must be numeric only

**Validation Rules**:
- UID must be numeric only
- Error prompt if format is incorrect

**Use Cases**:
- Participate in activities requiring Binance UID
- Submit Binance-related tasks

---

#### 5. `/bind_twitter @handle` - Bind X/Twitter Account

**Purpose**: Bind X (formerly Twitter) account

**Usage**:
```
/bind_twitter @yourhandle
```

**Parameters**:
- `@handle`: X/Twitter username, must start with `@`

**Validation Rules**:
- Must start with `@`
- Error prompt if format is incorrect

**Use Cases**:
- Participate in activities requiring Twitter account
- Submit Twitter-related tasks

---

#### 6. `/bind_address <address>` - Bind Community Account Address

**Purpose**: Bind community account address (e.g., wallet address)

**Usage**:
```
/bind_address your_address_here
```

**Parameters**:
- `<address>`: Account address, can be any string

**Notes**:
- Current version has no format validation, recommend entering correct address format
- Address will be saved directly to database

**Use Cases**:
- Bind wallet address
- Bind other community accounts

---

#### 7. `/invites` - View Invite Information

**Purpose**: View successful invite count and exclusive invite link

**Usage**:
```
/invites
```

**Displayed Content**:
- Successful invite count (invited users who have joined the group)
- Exclusive invite link
- Join group button (if group link is configured)

**Reward Mechanism**:
- When invitee first signs in the group, inviter receives point reward (configurable `INVITE_REWARD_POINTS`)

**Use Cases**:
- View invite promotion results
- Get invite link for promotion

---

#### 8. `/submit` - Submit Activity Link

**Purpose**: Submit Binance or Twitter article links to participate in activities

**Usage**:
```
/submit
```

**Process**:
1. Send `/submit` command
2. Select activity to participate in (loaded from `campaigns.json`)
3. Select submission type (Binance or Twitter)
4. Enter or paste link
5. Confirm submission

**Submission Types**:
- Binance article link
- Twitter article link

**Notes**:
- Each activity can only submit once per type
- Links will be validated for format
- Can view submissions in `/my_submissions` after submitting

**Use Cases**:
- Participate in community activities
- Complete tasks to earn points

---

#### 9. `/my_submissions` - View Submitted Links

**Purpose**: View all your submitted activity links

**Usage**:
```
/my_submissions
```

**Displayed Content**:
- List of all submitted links
- Each link shows: Type (Binance/Twitter), Link, Campaign ID

**Use Cases**:
- Check submission records
- Confirm if already submitted

---

#### 10. `/price <symbol>` - Query Cryptocurrency Price

**Purpose**: Query current price of specified cryptocurrency

**Usage**:
```
/price BTC
/price ETH
/price BNB
```

**Parameters**:
- `<symbol>`: Cryptocurrency trading pair symbol (e.g., BTC, ETH, BNB)

**Features**:
- Get real-time price from configured API
- Support all cryptocurrencies traded on exchange
- API address can be configured in `config.jsonc`

**Use Cases**:
- Query coin price
- View real-time market

---

#### 11. `/feedback <content>` - Send Feedback

**Purpose**: Send feedback, suggestions, or questions to administrators

**Usage**:
```
/feedback Enter your feedback content here
```

**Parameters**:
- `<content>`: Feedback content, can be any text

**Features**:
- Feedback content saved to `feedback.csv` file
- Administrators can export and view via `/export_feedback`

**Use Cases**:
- Report issues
- Make suggestions
- Request features

---

#### 12. `/unlock_points <amount>` - Unlock Points

**Purpose**: Unlock a portion of total points for transfer to other users

**Usage**:
```
/unlock_points 100
```

**Parameters**:
- `<amount>`: Number of points to unlock, must be positive integer

**Features**:
- Deduct specified amount from total points
- Add deducted points to unlocked points
- Unlocked points can be used for transfer

**Notes**:
- Unlocked points cannot be directly converted back to total points
- Ensure sufficient points available to unlock

**Use Cases**:
- Prepare to transfer to other users
- Unlock points before sending red packet

---

#### 13. `/transfer_points <recipient_id> <amount>` - Direct Transfer

**Purpose**: Directly transfer points to specified user

**Usage**:
```
/transfer_points 123456789 50
```

**Parameters**:
- `<recipient_id>`: Recipient's Telegram ID
- `<amount>`: Transfer point amount, must be positive integer

**Features**:
- Deducted from unlocked points
- Directly added to recipient's total points
- Transfer log recorded

**Notes**:
- Can only use unlocked points for transfer
- Need to know recipient's Telegram ID
- Transfer cannot be reversed

**Use Cases**:
- Quick transfer to known user
- Transfer without interactive confirmation

---

#### 14. `/transfer` - Interactive Transfer

**Purpose**: Transfer points through button interaction

**Usage**:
```
/transfer
```

**Process**:
1. Send `/transfer` command
2. Enter recipient's Telegram ID
3. Enter transfer amount
4. Confirm transfer information
5. Complete transfer

**Features**:
- Step-by-step confirmation to reduce errors
- Display transfer details for confirmation
- Transfer records saved

**Use Cases**:
- Transfer requiring confirmation
- When unfamiliar with command format

---

#### 15. `/transfers` - View Transfer History

**Purpose**: View your transfer history records

**Usage**:
```
/transfers
```

**Displayed Content**:
- Transfer record list (recent records)
- Each record shows: Recipient ID, Transfer Amount, Time

**Use Cases**:
- View transfer history
- Verify transfer records

---

#### 16. `/recent_points [limit]` - View Recent Extra Points

**Purpose**: View recent extra points earned

**Usage**:
```
/recent_points
/recent_points 20
```

**Parameters**:
- `[limit]`: Optional, number of records to display, default 10, maximum 50

**Displayed Content**:
- Recent extra points records
- Each record shows: Point amount, Reason, Time
- Total points in last 7 days
- Total points in last 30 days

**Use Cases**:
- View points earning records
- Verify points source

---

#### 17. `/faq` - Frequently Asked Questions

**Purpose**: View FAQ answers

**Usage**:
```
/faq
```

**Features**:
- Display FAQ category list
- Click category to view questions in that category
- Click question to view detailed answer
- FAQ content loaded from `faq.json` file

**Use Cases**:
- Find answers to questions
- Learn how to use features

---

#### 18. `/help` - Help Command

**Purpose**: View descriptions of all available commands

**Usage**:
```
/help
```

**Displayed Content**:
- User command list (private chat)
- Group command list
- Admin command list (visible only to admins)

**Use Cases**:
- View all available commands
- Learn command purposes

---

### Group Commands

The following commands can be used in the specified group (`ALLOWED_GROUP_ID`).

#### 1. `/signinword` - View Today's Sign-in Word

**Purpose**: View today's sign-in word

**Usage**:
```
/signinword
```

**Features**:
- Display today's sign-in word
- Display points ranking information
- Display consecutive sign-in reward information

**Use Cases**:
- View sign-in word when forgotten
- Learn sign-in reward rules

---

#### 2. `/ranking` - View Points Ranking

**Purpose**: View monthly points ranking

**Usage**:
```
/ranking
```

**Displayed Content**:
- Monthly points ranking (Top 10)
- Each user shows: Rank, Name, Points
- Administrators not shown in ranking

**Use Cases**:
- View points ranking
- Understand community activity

---

#### 3. `/active` - View Activity Ranking

**Purpose**: View monthly activity ranking

**Usage**:
```
/active
```

**Displayed Content**:
- Monthly activity ranking (Top 10)
- Activity based on points calculation, with minimum points requirement (`MIN_ACTIVE_POINTS`)
- Administrators not shown in ranking

**Use Cases**:
- View active user ranking
- Understand community participation

---

#### 4. `/price <symbol>` - Query Price (Group Version)

**Purpose**: Query cryptocurrency price in group

**Usage**:
```
/price BTC
```

**Features**:
- Same functionality as private chat version
- Results sent to group

---

#### 5. Daily Sign-in

**Purpose**: Sign in daily by sending sign-in word

**Usage**:
Send the day's sign-in word in the group (randomly selected from `signin_words.txt`)

**Features**:
- Bot publishes sign-in word daily at specified time (`SIGNIN_WORD_TIME`)
- Users send matching sign-in word to complete sign-in
- Sign-in success earns points (`SIGNIN_POINTS`)
- 7 consecutive days sign-in earns extra reward (`SIGNIN_BONUS_POINTS`)
- Sign-in word pinned for 5 minutes

**Reward Mechanism**:
- Daily sign-in: Earn base points
- 7 consecutive days: Earn extra reward points
- First group sign-in: Inviter earns reward points

**Use Cases**:
- Daily sign-in to earn points
- Participate in community activities

---

#### 6. Chat Points

**Purpose**: Earn points by chatting in group

**Features**:
- Sending text messages earns points (`CHAT_POINTS`)
- 1-minute cooldown to prevent spam
- Administrators also earn chat points
- If `CHAT_POINTS` is set to 0, this feature is disabled

**Use Cases**:
- Normal group chat
- Participate in discussions

---

#### 7. Quiz Activities

**Purpose**: Participate in quiz activities published by administrators

**Usage**:
After administrator publishes question, click option button to select answer

**Features**:
- Administrators publish questions via `/quiz_send`
- Questions randomly selected from `quiz_bank.json`
- Correct answer earns points (`QUIZ_CORRECT_POINTS`)
- Each question can only be answered once
- Question valid for 30 minutes

**Use Cases**:
- Participate in community quiz activities
- Earn extra points

---

#### 8. Red Packet Feature

**Purpose**: Send and claim point red packets

**Send Red Packet**:
```
/hongbao <total_points> <count>
or
/redpack <total_points> <count>
```

**Parameters**:
- `<total_points>`: Total red packet points (must be positive integer)
- `<count>`: Number of packets (how many shares)

**Claim Red Packet**:
- Click "Claim" button in red packet message
- Each red packet can only be claimed once
- Points randomly distributed
- Each user has anti-spam limit (cannot click repeatedly within 1 second)

**Features**:
- Use unlocked points to send red packet
- Red packet points randomly distributed to claimers
- Red packet displays sender information
- Red packet valid for 24 hours
- Unclaimed red packets after 24 hours automatically expire
- Remaining points from expired red packets automatically refunded to sender's unlocked points

**Red Packet Rules**:
- Red packet valid for 24 hours after creation
- Red packets unclaimed after 24 hours automatically expire
- Remaining points after expiration automatically refunded to sender at specified time daily (`REDPACKET_REFUND_TIME`, default 01:00)
- Refunded points added to sender's unlocked points
- Expired red packets cannot be claimed

**Notes**:
- Need to unlock sufficient points before sending red packet
- Red packet points randomly distributed, last share gets all remaining points
- If red packet not fully claimed, remaining points automatically refunded after expiration

**Use Cases**:
- Celebration activities
- Community interaction
- Share points

---

## Admin Commands

The following commands can only be used by administrators (need to be configured in `ADMIN_IDS` in `config.jsonc`).

### Points Management

#### 1. `/add_points <user_id> <amount>` - Add Points to User

**Purpose**: Add points to specified user's total points

**Usage**:
```
/add_points 123456789 100
```

**Parameters**:
- `<user_id>`: User's Telegram ID
- `<amount>`: Number of points to add

**Features**:
- Directly added to user's total points
- Operation logged
- Sensitive operation, use with caution

**Use Cases**:
- Activity rewards
- Compensate points
- Special rewards

---

#### 2. `/add_unlock_points <user_id> <amount>` - Add Unlocked Points to User

**Purpose**: Add unlocked points to specified user (can be used for transfer)

**Usage**:
```
/add_unlock_points 123456789 50
```

**Parameters**:
- `<user_id>`: User's Telegram ID
- `<amount>`: Number of unlocked points to add

**Features**:
- Directly added to user's unlocked points
- Unlocked points can be used for transfer
- Operation logged

**Use Cases**:
- Transfer rewards
- Special unlocked points distribution

---

#### 3. Batch Add Points (Upload CSV File)

**Purpose**: Batch add points to users via CSV file upload

**Usage**:
1. Prepare CSV file with format:
   ```csv
   telegram_id,points
   123456789,100
   987654321,50
   ```
2. Name file as `batch_points.csv`
3. Send file to bot in private chat

**Features**:
- Support batch processing multiple users
- Automatically validate user ID and points format
- Operation logged

**Use Cases**:
- Large-scale activity rewards
- Batch compensation
- Data migration

---

### Content Management

#### 4. `/quiz_send [json]` - Publish Quiz

**Purpose**: Publish quiz activity in group

**Usage**:
```
/quiz_send
```
or
```
/quiz_send {"question":"Question","options":["A.Option1","B.Option2"],"answer":0}
```

**Features**:
- Without parameter: Randomly select question from `quiz_bank.json`
- With JSON parameter: Use specified question
- Question published in group, users click options to answer
- Correct answer earns points, each question can only be answered once
- Question valid for 30 minutes

**Question Format**:
```json
{
  "question": "Question content",
  "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
  "answer": 0
}
```
- `question`: Question text
- `options`: Option array (usually A-D)
- `answer`: Correct answer index (starting from 0)

**Use Cases**:
- Publish quiz activities
- Community interaction
- Knowledge contests

---

#### 5. `/add_sensitive <word>` - Add Sensitive Word

**Purpose**: Add sensitive word to filter list

**Usage**:
```
/add_sensitive advertisement
```

**Parameters**:
- `<word>`: Sensitive word to add

**Features**:
- Added to `sensitive_words.txt` file
- Group messages containing sensitive words automatically deleted
- Warning message sent after deletion (auto-deleted after 15 seconds)
- Prompt if sensitive word already exists

**Use Cases**:
- Filter advertisements
- Filter inappropriate content
- Maintain group order

---

### Data Export

#### 6. `/export_users` - Export User Data

**Purpose**: Export all user data as CSV file

**Usage**:
```
/export_users
```

**Exported Content**:
- Telegram ID
- Last Sign-in Time
- Points
- Binance UID
- X Account
- Community Account Address
- Inviter ID
- Joined Group
- Name
- Custom ID
- Last Bonus Date
- Unlocked Points

**Use Cases**:
- Data analysis
- Data backup
- Generate reports

---

#### 7. `/export_submissions` - Export Submission Data

**Purpose**: Export all user submitted activity links

**Usage**:
```
/export_submissions
```

**Exported Content**:
- Telegram ID
- Submission Type (Binance/Twitter)
- Link
- Campaign ID
- Submission Time

**Use Cases**:
- Review submission content
- Statistics on activity participation
- Data backup

---

#### 8. `/export_submissions_by_campaign <campaign_id>` - Export Submissions by Campaign

**Purpose**: Export all submissions for specified campaign

**Usage**:
```
/export_submissions_by_campaign campaign001
```

**Parameters**:
- `<campaign_id>`: Campaign ID (defined in `campaigns.json`)

**Use Cases**:
- Review specific campaign submissions
- Campaign data statistics

---

#### 9. `/export_feedback` - Export Feedback Data

**Purpose**: Export all user feedback

**Usage**:
```
/export_feedback
```

**Exported Content**:
- User ID
- Feedback Content
- Feedback Time

**Use Cases**:
- View user feedback
- Handle issues
- Data analysis

---

#### 10. `/export_month_rank <YYYY-MM>` - Export Monthly Ranking

**Purpose**: Export points ranking for specified month

**Usage**:
```
/export_month_rank 2025-01
```

**Parameters**:
- `<YYYY-MM>`: Month format, e.g., `2025-01`

**Exported Content**:
- User Rank
- Telegram ID
- Points
- Snapshot Time

**Use Cases**:
- Monthly reports
- Reward distribution
- Data analysis

---

### Configuration Management

#### 11. Upload Configuration Files

**Purpose**: Upload various configuration files to update bot functionality

**Supported File Types**:

1. **`campaigns.json`** - Campaign Configuration
   ```json
   [
     {
       "id": "campaign001",
       "title": "Campaign Title",
       "desc": "Campaign Description",
       "deadline": "2025-12-31"
     }
   ]
   ```

2. **`faq.json`** - FAQ Configuration
   ```json
   {
     "categories": [
       {
         "title": "Category Title",
         "questions": [
           {
             "q": "Question",
             "a": "Answer"
           }
         ]
       }
     ]
   }
   ```

3. **`quiz_bank.json`** - Quiz Bank Configuration
   ```json
   [
     {
       "question": "Question",
       "options": ["A. Option 1", "B. Option 2"],
       "answer": 0
     }
   ]
   ```

**Usage**:
1. Prepare JSON file
2. Send file to bot in private chat
3. Bot automatically validates format and updates

**Use Cases**:
- Update activity list
- Update FAQ
- Update quiz bank

---

### Other Admin Functions

#### 12. `/search_user <keyword>` - Search User

**Purpose**: Search user information by keyword

**Usage**:
```
/search_user 123456789
/search_user username
```

**Search Scope**:
- Telegram ID
- Username
- Custom ID (custom_id)
- Name

**Displayed Content**:
- List of matching users
- Each user shows: ID, Name, Points, Unlocked Points

**Use Cases**:
- Find user information
- User management
- Troubleshooting

---

#### 13. `/get_group_id` - Get Group ID

**Purpose**: Get current group ID (for configuration)

**Usage**:
```
/get_group_id
```

**Features**:
- Use in group
- Returns group ID and prints to server log
- Used to configure `ALLOWED_GROUP_ID`

**Use Cases**:
- Configure bot
- Set allowed groups

---

#### 14. `/draw <count> <id_list>` - Draw Function

**Purpose**: Randomly select winners from specified user list

**Usage**:
```
/draw 3 1001,1002,1003,1004,1005
```

**Parameters**:
- `<count>`: Number to draw
- `<id_list>`: User ID list, comma-separated

**Features**:
- Display draw animation
- Randomly select specified number of users
- No duplicate selection (without replacement)
- If requested count exceeds candidate count, all candidates selected

**Use Cases**:
- Activity draws
- Random selection
- Community activities

---

#### 15. `/faq_reload` - Reload FAQ

**Purpose**: Reload FAQ configuration file (no bot restart required)

**Usage**:
```
/faq_reload
```

**Features**:
- Re-read `faq.json` file
- Update FAQ content
- No bot restart required

**Use Cases**:
- Update FAQ and take effect immediately
- Test FAQ configuration

---

#### 16. `/news` - Manually Trigger News Broadcast

**Purpose**: Manually trigger news broadcast (if news feature enabled)

**Usage**:
```
/news
```

**Features**:
- Immediately execute news fetch and broadcast
- Requires `NEWS_ENABLED` to be `true`
- Read news sources from `rss_sources.json`

**Use Cases**:
- Test news feature
- Manually publish news

---

## Feature Descriptions

### Points System

#### Point Types
1. **Total Points**: All user points, including:
   - Earned from sign-in
   - Earned from quiz
   - Earned from chat
   - Invite rewards
   - Admin additions

2. **Unlocked Points**: Points that can be used for transfer
   - Unlocked from total points via `/unlock_points`
   - Admin can directly add
   - Used for transfer and red packets

#### Ways to Earn Points
1. **Daily Sign-in**: Send sign-in word to earn base points
2. **Consecutive Sign-in**: 7 consecutive days sign-in earns extra reward
3. **Chat Points**: Chat in group to earn (with cooldown)
4. **Quiz Rewards**: Correct answer earns points
5. **Invite Rewards**: Invitee first sign-in, inviter earns reward
6. **Admin Addition**: Admin manually adds points

#### Point Usage
1. **Transfer**: Transfer to other users
2. **Red Packet**: Send red packet to share points
3. **Ranking**: Participate in points and activity rankings

#### Red Packet Points Notes
- Sending red packet requires unlocked points
- If red packet not fully claimed, remaining points automatically refunded after expiration
- Refunded points added to sender's unlocked points
- Ensures points are not lost

---

### Sign-in System

#### Sign-in Process
1. Bot publishes sign-in word daily at specified time (`SIGNIN_WORD_TIME`)
2. Sign-in word randomly selected from `signin_words.txt`
3. Users send matching sign-in word in group
4. Bot validates and rewards points
5. Sign-in word pinned for 5 minutes

#### Sign-in Rewards
- **Base Reward**: Each sign-in earns `SIGNIN_POINTS` points
- **Consecutive Reward**: 7 consecutive days sign-in earns `SIGNIN_BONUS_POINTS` extra points
- **Invite Reward**: Invitee first sign-in, inviter earns `INVITE_REWARD_POINTS` points

---

### Activity System

#### Activity Configuration
Activities configured via `campaigns.json` file:
```json
[
  {
    "id": "campaign001",
    "title": "Activity Title",
    "desc": "Activity Description",
    "deadline": "2025-12-31"
  }
]
```

#### Submission Process
1. User uses `/submit` to select activity
2. Select submission type (Binance/Twitter)
3. Enter link
4. Confirm submission
5. Each activity can only submit once per type

---

### Sensitive Word Filtering

#### Features
- Automatically detect sensitive words in group messages
- Messages containing sensitive words automatically deleted
- Warning message sent (auto-deleted after 15 seconds)
- Sensitive word list saved in `sensitive_words.txt`

#### Management
- Admin uses `/add_sensitive <word>` to add
- Directly edit `sensitive_words.txt` file

---

### Red Packet System

#### Red Packet Mechanism
- **Validity Period**: Red packet valid for 24 hours after creation
- **Expiration Handling**: Red packets over 24 hours automatically expire
- **Refund Mechanism**: Remaining points from expired red packets automatically refunded to sender
- **Refund Time**: Automatically executed daily at specified time (`REDPACKET_REFUND_TIME`, default 01:00)
- **Refund Method**: Remaining points added to sender's unlocked points

#### Red Packet Rules
1. **Sending Requirements**:
   - Must use unlocked points to send red packet
   - Total points and count must be positive integers
   - Immediately deducted from unlocked points after sending

2. **Claiming Rules**:
   - Each red packet can only be claimed once per user
   - Points randomly distributed, last share gets all remaining points
   - Anti-spam limit (cannot click repeatedly within 1 second)

3. **Expiration Handling**:
   - Red packet automatically expires 24 hours after creation
   - Cannot be claimed after expiration
   - Remaining points automatically refunded at specified time daily

#### Red Packet Refund Process
1. System automatically checks at specified time daily (default 01:00)
2. Find all red packets over 24 hours old and not marked as expired
3. Check if there are remaining points (`remaining_points > 0`)
4. Refund remaining points to sender's (`sender_id`) unlocked points
5. Mark red packet as expired (`expired = 1`)
6. Record detailed logs

---

### Scheduled Tasks

#### News Broadcast
- **Time**: `NEWS_BROADCAST_TIME` (default 09:00)
- **Function**: Fetch news from RSS sources and broadcast
- **Switch**: `NEWS_ENABLED`

#### Sign-in Word Publishing
- **Time**: `SIGNIN_WORD_TIME` (default 09:05)
- **Function**: Select and publish daily sign-in word
- **Switch**: `SIGNIN_WORD_ENABLED`

#### Price Update
- **Time**: `PRICE_UPDATE_TIME` (default 00:00)
- **Function**: Update daily opening price

#### Price Broadcast
- **Interval**: `PRICE_BROADCAST_INTERVAL_HOURS` (default 2 hours)
- **Function**: Broadcast price changes
- **Switch**: `PRICE_BROADCAST_ENABLED`

#### Red Packet Refund Check
- **Time**: `REDPACKET_REFUND_TIME` (default 01:00)
- **Function**: Check expired red packets and refund remaining points to sender
- **Description**: Automatically executed daily, processing red packets over 24 hours old that are not fully claimed
- **Processing Content**:
  - Find all expired and unprocessed red packets
  - Refund remaining points to sender's unlocked points
  - Mark red packet as expired
  - Record processing logs

---

## Configuration Guide

### Configuration File: `config.jsonc`

#### Basic Configuration
- `BOT_TOKEN`: Telegram Bot Token
- `ADMIN_IDS`: Administrator Telegram ID list
- `ALLOWED_GROUP_ID`: Allowed group ID for operations

#### Points Configuration
- `SIGNIN_POINTS`: Daily sign-in points (default 1)
- `SIGNIN_BONUS_POINTS`: 7 consecutive days sign-in reward (default 2)
- `QUIZ_CORRECT_POINTS`: Correct quiz answer points (default 1)
- `CHAT_POINTS`: Chat points (default 0, 0 means disabled)
- `INVITE_REWARD_POINTS`: Invite reward points (default 3)

#### Scheduled Tasks Configuration
- `NEWS_ENABLED`: Enable/disable news broadcast
- `SIGNIN_WORD_ENABLED`: Enable/disable sign-in word feature
- `PRICE_BROADCAST_ENABLED`: Enable/disable price broadcast
- `NEWS_BROADCAST_TIME`: News broadcast time (HH:MM)
- `SIGNIN_WORD_TIME`: Sign-in word publish time (HH:MM)
- `PRICE_UPDATE_TIME`: Price update time (HH:MM)
- `PRICE_BROADCAST_INTERVAL_HOURS`: Price broadcast interval (hours)
- `REDPACKET_REFUND_TIME`: Red packet refund check time (HH:MM, default 01:00)

#### Community Information
- `COMMUNITY_NAME`: Community name
- `COMMUNITY_GROUP_LINK`: Group link
- `COMMUNITY_ACCOUNT_NAME`: Community account name (e.g., wallet name)
- `DEFAULT_LANGUAGE`: Default language (zh_CN or en_US)

#### API Configuration
- `PRICE_API_BASE_URL`: Price API address

---

### Data Files

#### `signin_words.txt`
Daily sign-in word list, one word per line, supports Chinese and English.

#### `sensitive_words.txt`
Sensitive word list, one word per line.

#### `campaigns.json`
Activity configuration file, defines activities that can be participated in.

#### `faq.json`
FAQ configuration file, defines frequently asked questions and answers.

#### `quiz_bank.json`
Quiz bank configuration file, defines quiz activity questions.

#### `rss_sources.json`
RSS news source configuration (if news feature enabled).

#### `activities.json`
Activity matching configuration, used to automatically match user messages.

---

## Important Notes

1. **Private Chat Commands**: Most user commands can only be used in private chat
2. **Group Restrictions**: Group commands can only be used in configured group (`ALLOWED_GROUP_ID`)
3. **Admin Permissions**: Admin commands require ID in `ADMIN_IDS`
4. **Point Transfer**: Can only use unlocked points for transfer
5. **Sign-in Limit**: Can only sign in once per day
6. **Quiz Limit**: Each question can only be answered once
7. **File Format**: Uploaded configuration files must be valid JSON format
8. **Data Backup**: Recommend regular data export for backup
9. **Red Packet Validity**: Red packets valid for 24 hours, remaining points automatically refunded to sender after expiration
10. **Red Packet Refund**: System automatically checks and refunds remaining points from expired red packets daily, no manual operation required

---

## Technical Support

For questions or suggestions, please use `/feedback` command to send feedback.

---

*Last Updated: 2025*

