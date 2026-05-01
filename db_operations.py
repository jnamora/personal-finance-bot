"""
DynamoDB operations for Telegram Finance Bot
Handles all database CRUD operations
"""

import boto3
import uuid
import time
import logging
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from config import (
    DYNAMODB_TABLE_NAME,
    USER_PREFIX,
    TRANSACTION_PREFIX,
    TRANSACTION_PREFIX,
    TYPE_DESPESA,
    TYPE_RECEITA
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def create_transaction(user_id, transaction_type, amount, description=None, category=None, custom_date=None):
    """
    Create a new transaction in DynamoDB

    Args:
        user_id (int): Telegram user ID
        transaction_type (str): 'despesa' or 'receita'
        amount (Decimal): Transaction amount
        description (str): Transaction description (optional)
        category (str): Transaction category (optional)
        custom_date (datetime): Optional custom date for the transaction

    Returns:
        dict: Created transaction item
    """
    try:
        # Generate unique IDs
        transaction_id = str(uuid.uuid4())
        
        if custom_date:
            # Use custom date
            now = custom_date
            # For timestamp, we set the time to 12:00:00 of that day to avoid ordering confusion
            # or just use the current time but on that day? 
            # Let's use 12:00:00 to be consistent for backdated items
            ts_dt = now.replace(hour=12, minute=0, second=0, microsecond=0)
            timestamp_ms = int(ts_dt.timestamp() * 1000)
        else:
            # Use current time
            now = datetime.now()
            timestamp_ms = int(time.time() * 1000)

        # Create item structure
        item = {
            'PK': f'{USER_PREFIX}{user_id}',
            'SK': f'{TRANSACTION_PREFIX}{timestamp_ms}',
            'transaction_id': transaction_id,
            'type': transaction_type,
            'amount': amount,
            'date_str': now.strftime('%Y-%m-%d'),
            'month': now.strftime('%Y-%m'),
            'year': now.strftime('%Y'),
            'timestamp': timestamp_ms
        }

        # Add optional fields
        if description:
            item['description'] = description

        if category:
            item['category'] = category
        else:
            item['category'] = None

        # Put item in DynamoDB
        table.put_item(Item=item)

        logger.info(f"Created transaction: {transaction_id} for user {user_id} on {item['date_str']}")
        return item

    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        raise


def update_transaction_category(pk, sk, category):
    """
    Update the category of an existing transaction

    Args:
        pk (str): Partition key (USER#id)
        sk (str): Sort key (TRANS#timestamp)
        category (str): New category name

    Returns:
        bool: True if successful
    """
    try:
        # Update the category directly with keys (no scan needed!)
        table.update_item(
            Key={
                'PK': pk,
                'SK': sk
            },
            UpdateExpression='SET category = :cat',
            ExpressionAttributeValues={
                ':cat': category
            }
        )

        logger.info(f"Updated category to {category} for {pk}/{sk}")
        return True

    except Exception as e:
        logger.error(f"Error updating transaction category: {str(e)}")
        raise






def get_transactions_by_period(user_id, year=None, month=None):
    """
    Query transactions for a user filtered by period

    Args:
        user_id (int): Telegram user ID
        year (str): Year filter (e.g., '2025')
        month (str): Month filter (e.g., '2025-10')

    Returns:
        list: List of transaction items
    """
    try:
        pk = f'{USER_PREFIX}{user_id}'

        # Query all transactions for user
        response = table.query(
            KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with(TRANSACTION_PREFIX)
        )

        items = response['Items']

        # Continue querying if there are more pages
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with(TRANSACTION_PREFIX),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])

        # Filter by period
        filtered_items = items

        if month:
            filtered_items = [item for item in filtered_items if item.get('month') == month]
        elif year:
            filtered_items = [item for item in filtered_items if item.get('year') == year]

        logger.info(f"Retrieved {len(filtered_items)} transactions for user {user_id}")
        return filtered_items

    except Exception as e:
        logger.error(f"Error querying transactions: {str(e)}")
        raise


def calculate_summary(transactions):
    """
    Calculate financial summary from transactions

    Args:
        transactions (list): List of transaction items

    Returns:
        dict: Summary with totals, breakdown, and individual transactions by category
    """
    try:
        total_receitas = Decimal('0')
        total_despesas = Decimal('0')
        total_poupanca = Decimal('0')
        category_breakdown = {}
        category_transactions = {}  # Store individual transactions per category (despesas)
        receita_transactions = []  # Store individual income transactions
        poupanca_transactions = []  # Store individual savings/investment transactions

        for trans in transactions:
            amount = Decimal(str(trans['amount']))
            trans_type = trans['type']

            if trans_type == TYPE_RECEITA:
                total_receitas += amount

                # Track individual receitas
                receita_transactions.append({
                    'description': trans.get('description', 'Sem descrição'),
                    'amount': amount,
                    'date': trans.get('date_str', '')
                })

            elif trans_type == TYPE_DESPESA:
                # Track by category
                category = trans.get('category', 'Sem Categoria')
                if category is None:
                    category = 'Sem Categoria'

                # Separate Poupança e Investimento from regular expenses
                if category == "📈 Investments":
                    total_poupanca += amount
                    poupanca_transactions.append({
                        'description': trans.get('description', 'Sem descrição'),
                        'amount': amount,
                        'date': trans.get('date_str', '')
                    })
                else:
                    total_despesas += amount

                    if category not in category_breakdown:
                        category_breakdown[category] = Decimal('0')
                        category_transactions[category] = []

                    category_breakdown[category] += amount

                    # Add individual transaction details
                    category_transactions[category].append({
                        'description': trans.get('description', 'Sem descrição'),
                        'amount': amount,
                        'date': trans.get('date_str', '')
                    })

        saldo = total_receitas - total_despesas - total_poupanca

        return {
            'total_receitas': total_receitas,
            'total_despesas': total_despesas,
            'total_poupanca': total_poupanca,
            'saldo': saldo,
            'count': len(transactions),
            'breakdown': category_breakdown,
            'transactions_by_category': category_transactions,
            'receita_transactions': receita_transactions,
            'poupanca_transactions': poupanca_transactions
        }

    except Exception as e:
        logger.error(f"Error calculating summary: {str(e)}")
        raise


def get_recent_transactions(user_id, limit=5):
    """
    Get recent transactions for a user

    Args:
        user_id (int): Telegram user ID
        limit (int): Number of recent transactions to retrieve

    Returns:
        list: List of recent transaction items, sorted by newest first
    """
    try:
        pk = f'{USER_PREFIX}{user_id}'

        # Query all transactions for user, sorted by SK descending (newest first)
        response = table.query(
            KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with(TRANSACTION_PREFIX),
            ScanIndexForward=False,  # Sort descending (newest first)
            Limit=limit
        )

        items = response['Items']
        logger.info(f"Retrieved {len(items)} recent transactions for user {user_id}")
        return items

    except Exception as e:
        logger.error(f"Error querying recent transactions: {str(e)}")
        raise


def search_transactions(user_id, amount, description=None):
    """
    Search for transactions matching amount and optionally description

    Args:
        user_id (int): Telegram user ID
        amount (Decimal): Transaction amount to search for
        description (str, optional): Description to search for (case-insensitive partial match)

    Returns:
        list: List of matching transaction items
    """
    try:
        pk = f'{USER_PREFIX}{user_id}'

        # Query all transactions for user
        response = table.query(
            KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with(TRANSACTION_PREFIX)
        )

        items = response['Items']

        # Continue querying if there are more pages
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with(TRANSACTION_PREFIX),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])

        # Filter by amount and optionally description
        matching_items = []

        for item in items:
            item_amount = Decimal(str(item['amount']))

            # Match exact amount
            if item_amount == amount:
                # If description provided, filter by it as well
                if description:
                    description_lower = description.lower()
                    item_description = item.get('description', '').lower()
                    if description_lower in item_description:
                        matching_items.append(item)
                else:
                    # No description filter, just match by amount
                    matching_items.append(item)

        logger.info(f"Found {len(matching_items)} matching transactions for user {user_id}")
        return matching_items

    except Exception as e:
        logger.error(f"Error searching transactions: {str(e)}")
        raise


def delete_transaction(pk, sk):
    """
    Delete a transaction by its keys

    Args:
        pk (str): Partition key
        sk (str): Sort key

    Returns:
        bool: True if successful
    """
    try:
        # Delete the transaction directly (no scan needed!)
        table.delete_item(
            Key={
                'PK': pk,
                'SK': sk
            }
        )

        logger.info(f"Deleted transaction: {pk}/{sk}")
        return True

    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        raise
