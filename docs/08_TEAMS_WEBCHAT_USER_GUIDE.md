# Teams & Web Chat User Guide

## Overview

This guide explains all the features available to end users interacting with the Genie Bot through Microsoft Teams or Web Chat.

---

## Getting Started

### First Time Setup

1. **Find the Bot**
   - Open Microsoft Teams
   - Click "Apps" in the sidebar
   - Search for "Genie Bot" (or your organization's bot name)
   - Click "Add" to start a conversation

2. **Sign In**
   - The first time you ask a question, you'll be prompted to sign in
   - Click the "Sign In" button
   - Complete the Azure AD authentication
   - Your session is now active

### Welcome Message

When you first interact with the bot, you'll see:

```
Hello! I'm the Genie Bot. Ask me questions about your data.

Commands:
- Type your question to query Genie
- Type 'new' to start a new conversation
- Type 'history' to see recent conversations
- Type 'signout' to sign out
```

---

## Asking Questions

### Basic Queries

Simply type your question in natural language:

```
Show me total sales by region
```

The bot will:
1. Show a typing indicator while processing
2. Return results in a formatted table
3. Offer chart options if applicable
4. Suggest follow-up questions

### Follow-up Questions

Continue the conversation naturally:

```
User: Show me sales by region
Bot: [Returns table]

User: Now filter by Q4 2024
Bot: [Returns filtered table]

User: Which region had the highest growth?
Bot: [Returns analysis]
```

### Question Tips

| Good Questions | Avoid |
|---------------|-------|
| "Show me sales by product category" | "Get me everything" |
| "What was revenue in Q4 2024?" | "Show all data" |
| "Compare sales between regions" | "SELECT * FROM table" |
| "Who are my top 10 customers?" | SQL syntax |

---

## Understanding Results

### Table Format

Query results appear as formatted tables:

```
| region  | total_sales | order_count |
|---------|-------------|-------------|
| East    | 125,000     | 450         |
| West    | 98,000      | 380         |
| North   | 87,500      | 320         |
| South   | 76,000      | 290         |

Showing 4 of 4 rows
```

### Analysis Description

The bot often provides context:

```
**Analysis:** Total sales aggregated by region for the current quarter.

| region  | total_sales |
|---------|-------------|
...
```

### SQL Code

Sometimes the generated SQL is shown:

```sql
SELECT region, SUM(amount) as total_sales
FROM sales.orders
WHERE quarter = 'Q4'
GROUP BY region
ORDER BY total_sales DESC
```

---

## Visualization Features

### Chart Generation

When data is suitable for visualization, you'll see a button:

```
┌─────────────────────────────────────┐
│ 📊 Chart available (bar chart)     │
├─────────────────────────────────────┤
│ [📊 Show Bar Chart] [📄 Download CSV]│
└─────────────────────────────────────┘
```

Click "Show Bar Chart" to see the visualization.

### Chart Types

| Type | Best For | Example |
|------|----------|---------|
| 📊 Bar | Comparing categories | Sales by region |
| 📈 Line | Trends over time | Monthly revenue |
| 🥧 Pie | Proportions (≤10 items) | Market share |
| ⚫ Scatter | Correlations | Price vs. quantity |
| 📉 Histogram | Distributions | Order value distribution |

### Switching Chart Types

After a chart is shown, you can change the type:

```
┌─────────────────────────────────────┐
│ [📊 Bar] [📈 Line] [🥧 Pie]        │
│ [⬇️ Download PNG] [📄 Download CSV] │
└─────────────────────────────────────┘
```

### Downloading Data

| Button | Result |
|--------|--------|
| 📄 Download CSV | Spreadsheet-compatible file |
| ⬇️ Download PNG | Chart image |

---

## Conversation Management

### How Conversations Work

**Important**: Conversations are stored in Databricks, not locally. This means:

- Your conversation history persists even if the bot restarts
- After signing out and signing back in, you can resume where you left off
- Conversations are tied to your user identity (email)
- Each follow-up question automatically continues your most recent conversation

### Commands

| Command | Action |
|---------|--------|
| `new` | Start a fresh conversation (clears local context) |
| `reset` | Same as 'new' |
| `history` | List your 5 most recent conversations |
| `list` | Same as 'history' |
| `signout` | Sign out and clear your tokens |
| `logout` | Same as 'signout' |

### Starting Fresh

Type `new` or `reset` to start a fresh conversation:

```
User: new

Bot: Conversation reset. Next question starts fresh.
```

This clears the local conversation reference. Your next question will either:
- Start a brand new conversation, or
- Resume your most recent Databricks conversation (automatic)

### Conversation History

Type `history` to see your recent conversations:

```
Your Recent Conversations:

1. Sales Analysis Q4 (ID: abc12345...)
2. Customer Segmentation (ID: def67890...)
3. Product Performance (ID: ghi11111...)
4. Revenue Trends (ID: jkl22222...)
5. Customer Churn Analysis (ID: mno33333...)
```

### Automatic Resumption

The bot automatically resumes your most recent conversation when:

1. **You sign in again** after being signed out
2. **The bot restarts** (deployed update, Azure restart, etc.)
3. **Your session expires** and you re-authenticate

This happens silently - you simply continue asking questions and the bot picks up where you left off.

To force a fresh start, type `new` before your next question.

---

## Suggested Questions

After results, the bot may suggest follow-up questions:

```
💡 You might also want to ask:

[📌 Show this by month]
[📌 Compare to last year]
[📌 Which product category is highest?]
```

Click any suggestion to ask that question immediately.

---

## Data Security

### What You See

**Important**: You only see data you're authorized to access.

- Row-Level Security is enforced automatically
- Your query runs with YOUR identity
- Results are filtered to YOUR data only

### Example

If two users ask the same question:

```
Alice asks: "Show my orders"
→ Alice sees: Alice's orders only

Bob asks: "Show my orders"
→ Bob sees: Bob's orders only
```

### Sign Out

For security, sign out when done:
- Type `signout` or `logout`
- Your tokens are cleared
- Next query will require sign-in again

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Please sign in" keeps appearing | Clear Teams cache, try again |
| Query takes too long | Complex queries may take up to 10 minutes |
| "No data returned" | Check if you have access to the data |
| Chart won't generate | Data may not be suitable (>100 rows) |
| Bot not responding | Check your internet connection |

### Error Messages

| Message | Meaning |
|---------|---------|
| "Query timed out" | Query took >10 minutes |
| "Authentication failed" | Sign in expired, try again |
| "Service unavailable" | Databricks may be down |
| "Query failed" | SQL error in Genie |

### Getting Help

If issues persist:
1. Type `signout` and sign in again
2. Type `new` to start fresh
3. Contact your IT administrator

---

## Tips for Better Results

### Be Specific

```
❌ "Show me data"
✅ "Show me sales by product category for Q4 2024"
```

### Use Time Frames

```
❌ "Show recent orders"
✅ "Show orders from the last 30 days"
```

### Ask for Aggregations

```
❌ "List all transactions"
✅ "What is the total transaction value by customer?"
```

### Iterate

Start broad, then narrow down:

```
1. "Show sales by region"
2. "Focus on the East region"
3. "Show monthly trend for East"
4. "Compare to same period last year"
```

---

## Feature Comparison: Teams vs Web Chat

| Feature | Teams | Web Chat |
|---------|-------|----------|
| Natural language queries | ✅ | ✅ |
| Charts | ✅ | ✅ |
| CSV download | ✅ | ✅ |
| PNG download | ✅ | ✅ |
| Suggested questions | ✅ | ✅ |
| SSO sign-in | ✅ (Silent) | ✅ (Prompt) |
| Notifications | ✅ | ❌ |
| Mobile support | ✅ | ✅ |
| Offline access | ❌ | ❌ |

---

## Keyboard Shortcuts (Teams)

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line |
| Up Arrow | Edit last message |
| Ctrl+Shift+X | Insert emoji |

---

## Best Practices

1. **Start conversations fresh** when changing topics
2. **Use charts** for visual analysis
3. **Export to CSV** for further analysis in Excel
4. **Sign out** when finished for security
5. **Check suggested questions** for insights you might miss

---

## Sample Conversation

```
User: Hello

Bot: Hello! I'm the Genie Bot. Ask me questions about your data.
     Commands:
     - Type your question to query Genie
     - Type 'new' to start a new conversation
     ...

User: Show me my top 5 customers by revenue

Bot: **Analysis:** Top customers ranked by total revenue.

     | customer_name    | total_revenue |
     |------------------|---------------|
     | Acme Corp        | $125,000      |
     | Global Inc       | $98,500       |
     | Tech Solutions   | $87,200       |
     | DataFirst        | $76,800       |
     | CloudPro         | $65,400       |

     📊 Chart available (bar chart)
     [📊 Show Bar Chart] [📄 Download CSV]

     💡 You might also want to ask:
     [📌 Show revenue trend for these customers]
     [📌 What products do they buy most?]

User: [Clicks "Show revenue trend for these customers"]

Bot: [Displays line chart of revenue over time]
```
