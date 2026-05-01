# Telegram Finance Bot

A personal expenses tracker for Telegram, built for AWS Lambda with DynamoDB.

The bot lets you track expenses, income, history, and monthly/yearly summaries from Telegram commands. The user-facing bot messages are in Portuguese.

## Features

- Register expenses and income with optional custom dates
- Categorize expenses with Telegram inline buttons
- View recent transactions
- Delete transactions after confirmation
- Generate financial summaries by month or year
- Store data in DynamoDB

## Commands

```text
/start
/categorias
/despesa <amount> [YYYY-MM-DD] <description>
/receita <amount> [YYYY-MM-DD] <description>
/consulta [mes|ano|YYYY-MM]
/historico [limit]
/apagar <amount> [description]
```

Examples:

```text
/despesa 25.50 2026-01-15 groceries
/receita 1500 salary
/consulta mes
/historico 10
/apagar 25.50 groceries
```

## Project Structure

```text
lambda_function.py   Lambda entry point
bot_handlers.py      Telegram command handlers
db_operations.py     DynamoDB operations
config.py            Environment-based config and constants
requirements.txt     Python dependencies
tests/               Unit tests
```

## Configuration

Set these environment variables in AWS Lambda:

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name, defaults to `finance-transactions` |

Do not commit real tokens, `.env` files, packaged Lambda folders, or deployment ZIP files.

## Deployment Notes

1. Create a DynamoDB table with `PK` as the partition key and `SK` as the sort key.
2. Package the Lambda code with dependencies from `requirements.txt`.
3. Create or update the AWS Lambda function.
4. Connect API Gateway to the Lambda function.
5. Register the API Gateway URL as the Telegram webhook.
