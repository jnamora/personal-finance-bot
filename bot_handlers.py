"""
Telegram Bot Command Handlers
Contains logic for handling bot commands and callbacks
"""

import re
import logging
import requests
from decimal import Decimal, InvalidOperation
from datetime import datetime
from config import (
    TELEGRAM_API_BASE_URL,
    CATEGORIES,
    CATEGORY_EXPLANATIONS,
    CMD_DESPESA,
    CMD_RECEITA,
    CMD_CONSULTA,
    CMD_START,
    CMD_HISTORICO,
    CMD_APAGAR,
    CMD_CATEGORIAS,
    CALLBACK_CATEGORY_PREFIX,
    CALLBACK_DELETE_PREFIX,
    TYPE_DESPESA,
    TYPE_RECEITA,
    EMOJI_INCOME,
    EMOJI_EXPENSE,
    MSG_WELCOME,
    MSG_INVALID_AMOUNT,
    MSG_MISSING_DESCRIPTION,
    MSG_INVALID_PERIOD,
    MSG_NO_TRANSACTIONS,
    MSG_ERROR_OCCURRED,
    MSG_CATEGORY_UPDATED,
    MSG_TRANSACTION_DELETED,
    MSG_NO_MATCHING_TRANSACTIONS,
    get_expense_saved_message,
    get_income_saved_message,
    get_summary_message
)
from db_operations import (
    create_transaction,
    update_transaction_category,
    get_transactions_by_period,
    calculate_summary,
    get_recent_transactions,
    search_transactions,
    delete_transaction
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_message(chat_id, text, reply_markup=None):
    """
    Send a message to a Telegram chat

    Args:
        chat_id (int): Chat ID
        text (str): Message text
        reply_markup (dict): Optional inline keyboard markup

    Returns:
        dict: Response from Telegram API
    """
    # Telegram message limit is 4096 characters
    MAX_LENGTH = 4000  # Leave some margin

    if len(text) > MAX_LENGTH:
        # Truncate and add warning
        text = text[:MAX_LENGTH] + "\n\n... (mensagem truncada devido ao tamanho)"
        logger.warning(f"Message truncated from {len(text)} to {MAX_LENGTH} chars")

    url = f"{TELEGRAM_API_BASE_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }

    if reply_markup:
        payload['reply_markup'] = reply_markup

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise


def answer_callback_query(callback_query_id, text=None):
    """
    Answer a callback query from inline keyboard

    Args:
        callback_query_id (str): Callback query ID
        text (str): Optional notification text

    Returns:
        dict: Response from Telegram API
    """
    url = f"{TELEGRAM_API_BASE_URL}/answerCallbackQuery"
    payload = {
        'callback_query_id': callback_query_id
    }

    if text:
        payload['text'] = text

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error answering callback query: {str(e)}")
        raise


def parse_amount(amount_str):
    """
    Parse amount string to Decimal, handling Portuguese format

    Args:
        amount_str (str): Amount string (can use , or . as decimal separator)

    Returns:
        Decimal: Parsed amount or None if invalid
    """
    try:
        # Replace comma with period for Portuguese format
        normalized = amount_str.replace(',', '.')

        # Remove any spaces and euro symbols
        normalized = normalized.strip().replace('€', '').replace(' ', '')

        # Convert to Decimal
        amount = Decimal(normalized)

        # Validate positive and reasonable (max 1 million)
        if amount <= 0 or amount > Decimal('1000000'):
            return None

        # Round to 2 decimal places
        amount = amount.quantize(Decimal('0.01'))

        return amount
    except (InvalidOperation, ValueError):
        return None


def create_category_keyboard(pk, sk):
    """
    Create inline keyboard for category selection

    Args:
        pk (str): Partition key
        sk (str): Sort key

    Returns:
        dict: Inline keyboard markup
    """
    keyboard = []
    row = []

    # Encode PK and SK for callback (remove prefixes to save space)
    pk_short = pk.replace('USER#', '')
    sk_short = sk.replace('TRANS#', '')

    for i, category in enumerate(CATEGORIES):
        # Format: cat:pk:sk:category
        callback_data = f"{CALLBACK_CATEGORY_PREFIX}{pk_short}:{sk_short}:{category}"
        row.append({
            'text': category,
            'callback_data': callback_data
        })

        # Create rows of 2 buttons
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []

    # Add remaining button if odd number
    if row:
        keyboard.append(row)

    return {'inline_keyboard': keyboard}


def handle_start(chat_id, user_id):
    """
    Handle /start command

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID

    Returns:
        None
    """
    try:
        send_message(chat_id, MSG_WELCOME)
        logger.info(f"Sent welcome message to user {user_id}")
    except Exception as e:
        logger.error(f"Error handling /start: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def extract_date_and_description(args):
    """
    Extract date (YYYY-MM-DD) and remaining description from arguments.
    
    Args:
        args (list): List of strings (command parts after amount)
        
    Returns:
        tuple: (custom_date, description_str)
        custom_date is datetime object or None
    """
    custom_date = None
    desc_parts = []
    
    # regex for YYYY-MM-DD
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    
    for part in args:
        if not custom_date and date_pattern.match(part):
            try:
                custom_date = datetime.strptime(part, '%Y-%m-%d')
            except ValueError:
                # Invalid date (e.g., 2025-13-40), treat as text
                desc_parts.append(part)
        else:
            desc_parts.append(part)
            
    return custom_date, " ".join(desc_parts).strip()


def handle_despesa(chat_id, user_id, command_text):
    """
    Handle /despesa command

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID
        command_text (str): Full command text

    Returns:
        None
    """
    try:
        # Parse command: /despesa <valor> [data] <descrição>
        # Parts will be: ['/despesa', 'amount', 'word1', 'word2', ...]
        parts = command_text.split()  # Split by varying whitespace

        if len(parts) < 3:
            send_message(chat_id, MSG_MISSING_DESCRIPTION)
            return

        amount_str = parts[1]
        
        # Parse and validate amount first
        amount = parse_amount(amount_str)
        if amount is None:
            send_message(chat_id, MSG_INVALID_AMOUNT)
            return

        # Extract date and description from remaining parts
        remaining_parts = parts[2:]
        custom_date, description = extract_date_and_description(remaining_parts)
        
        # If description became empty because we only had a date
        if not description:
             send_message(chat_id, "❌ Descrição é obrigatória.")
             return

        # Validate description length
        if len(description) > 200:
            send_message(chat_id, "❌ Descrição demasiado longa (máximo 200 caracteres)")
            return

        if len(description) < 2:
            send_message(chat_id, "❌ Descrição demasiado curta (mínimo 2 caracteres)")
            return

        # Create transaction without category
        transaction = create_transaction(
            user_id=user_id,
            transaction_type=TYPE_DESPESA,
            amount=amount,
            description=description,
            category=None,
            custom_date=custom_date
        )

        # Send confirmation with category selection keyboard
        # Adjust message if date was custom
        msg_date = ""
        if custom_date:
            msg_date = f" ({custom_date.strftime('%Y-%m-%d')})"
            
        message_text = f"💸 Despesa registada{msg_date}: €{amount} - {description}\n\nEscolha a categoria:"
        
        keyboard = create_category_keyboard(transaction['PK'], transaction['SK'])

        send_message(chat_id, message_text, reply_markup=keyboard)
        logger.info(f"Created expense for user {user_id}: €{amount}")

    except Exception as e:
        logger.error(f"Error handling /despesa: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def handle_receita(chat_id, user_id, command_text):
    """
    Handle /receita command

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID
        command_text (str): Full command text

    Returns:
        None
    """
    try:
        # Parse command: /receita <valor> [data] <descrição>
        parts = command_text.split()

        if len(parts) < 3:
            send_message(chat_id, "❌ Descrição é obrigatória. Exemplo: /receita 1500 salário")
            return

        amount_str = parts[1]
        
        # Parse and validate amount
        amount = parse_amount(amount_str)
        if amount is None:
            send_message(chat_id, MSG_INVALID_AMOUNT)
            return
            
        # Extract date and description from remaining parts
        remaining_parts = parts[2:]
        custom_date, description = extract_date_and_description(remaining_parts)
        
        # If description became empty
        if not description:
             send_message(chat_id, "❌ Descrição é obrigatória.")
             return

        # Validate description length
        if len(description) > 200:
            send_message(chat_id, "❌ Descrição demasiado longa (máximo 200 caracteres)")
            return

        if len(description) < 2:
            send_message(chat_id, "❌ Descrição demasiado curta (mínimo 2 caracteres)")
            return

        # Create transaction
        create_transaction(
            user_id=user_id,
            transaction_type=TYPE_RECEITA,
            amount=amount,
            description=description,
            custom_date=custom_date
        )

        # Send confirmation
        msg_date = ""
        date_used = custom_date if custom_date else datetime.now()
        date_str = date_used.strftime('%Y-%m-%d')
        
        if custom_date:
            msg_date = f" ({date_str})"
            
        message_text = f"💰 Receita registada{msg_date}: €{amount} - {description}"
        send_message(chat_id, message_text)
        logger.info(f"Created income for user {user_id}: €{amount}")

    except Exception as e:
        logger.error(f"Error handling /receita: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def handle_consulta(chat_id, user_id, command_text):
    """
    Handle /consulta command

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID
        command_text (str): Full command text

    Returns:
        None
    """
    try:
        # Parse command: /consulta <periodo>
        parts = command_text.split(maxsplit=1)

        # Default to 'mes' (Salary Cycle) if no argument provided
        if len(parts) < 2:
            period = 'mes'
        else:
            period = parts[1].strip().lower()

        now = datetime.now()

        year = None
        month = None
        period_name = ""

        # Determine period and fetch transactions
        if period in ['mes', 'mês']:
            # Current Calendar Month
            year = now.strftime('%Y')
            month = now.strftime('%Y-%m')
            
            # Format nicely: December 2025
            period_name = now.strftime('%B %Y')
            transactions = get_transactions_by_period(user_id, month=month)
            
        elif period == 'ano':
            # Current year
            year = now.strftime('%Y')
            period_name = f"Ano {year}"
            transactions = get_transactions_by_period(user_id, year=year)

        else:
            # Try to parse YYYY-MM format
            match = re.match(r'^(\d{4})-(\d{2})$', period)
            if match:
                month = period
                try:
                    # Validate date
                    date_obj = datetime.strptime(period, '%Y-%m')
                    period_name = date_obj.strftime('%B %Y')
                    transactions = get_transactions_by_period(user_id, month=month)
                except ValueError:
                    send_message(chat_id, MSG_INVALID_PERIOD)
                    return
            else:
                send_message(chat_id, MSG_INVALID_PERIOD)
                return

        if not transactions:
            send_message(chat_id, MSG_NO_TRANSACTIONS)
            return

        # Calculate summary
        summary = calculate_summary(transactions)

        # Convert transactions_by_category to float amounts
        transactions_by_category = {}
        if 'transactions_by_category' in summary:
            for category, trans_list in summary['transactions_by_category'].items():
                transactions_by_category[category] = [
                    {
                        'description': t['description'],
                        'amount': float(t['amount']),
                        'date': t['date']
                    }
                    for t in trans_list
                ]

        # Convert receita_transactions to float amounts
        receita_transactions = []
        if 'receita_transactions' in summary:
            receita_transactions = [
                {
                    'description': t['description'],
                    'amount': float(t['amount']),
                    'date': t['date']
                }
                for t in summary['receita_transactions']
            ]

        # Convert poupanca_transactions to float amounts
        poupanca_transactions = []
        if 'poupanca_transactions' in summary:
            poupanca_transactions = [
                {
                    'description': t['description'],
                    'amount': float(t['amount']),
                    'date': t['date']
                }
                for t in summary['poupanca_transactions']
            ]

        # Generate and send message
        message_text = get_summary_message(
            period_name=period_name,
            total_receitas=float(summary['total_receitas']),
            total_despesas=float(summary['total_despesas']),
            saldo=float(summary['saldo']),
            count=summary['count'],
            breakdown={k: float(v) for k, v in summary['breakdown'].items()},
            transactions_by_category=transactions_by_category,
            receita_transactions=receita_transactions,
            total_poupanca=float(summary['total_poupanca']),
            poupanca_transactions=poupanca_transactions
        )

        send_message(chat_id, message_text)
        logger.info(f"Sent summary for user {user_id}, period {period_name}")

    except Exception as e:
        logger.error(f"Error handling /consulta: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def handle_callback_query(callback_query):
    """
    Handle callback query from inline keyboard

    Args:
        callback_query (dict): Callback query object from Telegram

    Returns:
        None
    """
    try:
        callback_id = callback_query['id']
        callback_data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']

        # Handle cancel button
        if callback_data == 'cancel':
            answer_callback_query(callback_id, "Cancelado")
            message_id = callback_query['message']['message_id']
            edit_message_reply_markup(chat_id, message_id)
            return

        # Parse callback data: cat:pk:sk:category
        if callback_data.startswith(CALLBACK_CATEGORY_PREFIX):
            parts = callback_data[len(CALLBACK_CATEGORY_PREFIX):].split(':', 2)

            if len(parts) == 3:
                pk_short = parts[0]
                sk_short = parts[1]
                category = parts[2]

                # Reconstruct full keys
                pk = f'USER#{pk_short}'
                sk = f'TRANS#{sk_short}'

                # Update category in database (no scan needed!)
                success = update_transaction_category(pk, sk, category)

                if success:
                    # Answer callback query
                    answer_callback_query(callback_id, MSG_CATEGORY_UPDATED)

                    # Update message to remove keyboard
                    message_id = callback_query['message']['message_id']
                    edit_message_reply_markup(chat_id, message_id)

                    logger.info(f"Updated category to {category}")
                else:
                    answer_callback_query(callback_id, MSG_ERROR_OCCURRED)
            else:
                answer_callback_query(callback_id, MSG_ERROR_OCCURRED)

        # Parse callback data: del:pk:sk
        elif callback_data.startswith(CALLBACK_DELETE_PREFIX):
            parts = callback_data[len(CALLBACK_DELETE_PREFIX):].split(':', 1)

            if len(parts) == 2:
                pk_short = parts[0]
                sk_short = parts[1]

                # Reconstruct full keys
                pk = f'USER#{pk_short}'
                sk = f'TRANS#{sk_short}'

                # Delete transaction from database (no scan needed!)
                success = delete_transaction(pk, sk)

                if success:
                    # Answer callback query
                    answer_callback_query(callback_id, MSG_TRANSACTION_DELETED)

                    # Update message to remove keyboard
                    message_id = callback_query['message']['message_id']
                    edit_message_reply_markup(chat_id, message_id)

                    logger.info(f"Deleted transaction")
                else:
                    answer_callback_query(callback_id, MSG_ERROR_OCCURRED)
            else:
                answer_callback_query(callback_id, MSG_ERROR_OCCURRED)

    except Exception as e:
        logger.error(f"Error handling callback query: {str(e)}")
        try:
            answer_callback_query(callback_query['id'], MSG_ERROR_OCCURRED)
        except:
            pass


def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    """
    Edit message reply markup (remove inline keyboard)

    Args:
        chat_id (int): Chat ID
        message_id (int): Message ID
        reply_markup (dict): Optional new markup

    Returns:
        dict: Response from Telegram API
    """
    url = f"{TELEGRAM_API_BASE_URL}/editMessageReplyMarkup"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }

    if reply_markup:
        payload['reply_markup'] = reply_markup

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error editing message markup: {str(e)}")
        # Don't raise - this is not critical
        pass


def handle_historico(chat_id, user_id, command_text):
    """
    Handle /historico command - view recent transactions

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID
        command_text (str): Full command text

    Returns:
        None
    """
    try:
        # Parse command: /historico [N]
        parts = command_text.split(maxsplit=1)

        # Default to 5 transactions
        limit = 5

        # If user specified a number
        if len(parts) > 1:
            try:
                limit = int(parts[1])
                # Cap at 50 to avoid huge messages
                if limit > 50:
                    limit = 50
                elif limit < 1:
                    limit = 5
            except ValueError:
                send_message(chat_id, "❌ Número inválido. Exemplo: /historico 20")
                return

        # Get recent transactions
        transactions = get_recent_transactions(user_id, limit=limit)

        if not transactions:
            send_message(chat_id, MSG_NO_TRANSACTIONS)
            return

        # Format message
        msg = f"📋 Últimas {len(transactions)} transações:\n\n"

        for trans in transactions:
            trans_type = trans['type']
            amount = float(trans['amount'])
            description = trans.get('description', 'Sem descrição')
            category = trans.get('category', 'Sem categoria')
            date_str = trans.get('date_str', '')

            if trans_type == TYPE_RECEITA:
                emoji = EMOJI_INCOME
                msg += f"{emoji} {date_str} - {description}: €{amount:.2f}\n"
            else:  # TYPE_DESPESA
                emoji = EMOJI_EXPENSE
                if category and category != 'Sem Categoria':
                    msg += f"{emoji} {date_str} - {description}: €{amount:.2f} ({category})\n"
                else:
                    msg += f"{emoji} {date_str} - {description}: €{amount:.2f}\n"

        send_message(chat_id, msg)
        logger.info(f"Sent history for user {user_id}, limit {limit}")

    except Exception as e:
        logger.error(f"Error handling /historico: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def handle_apagar(chat_id, user_id, command_text):
    """
    Handle /apagar command - delete transactions by amount and description

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID
        command_text (str): Full command text

    Returns:
        None
    """
    try:
        # Parse command: /apagar <valor> [descrição]
        parts = command_text.split(maxsplit=2)

        if len(parts) < 2:
            send_message(chat_id, "❌ Valor é obrigatório. Exemplo: /apagar 25.50 ou /apagar 25.50 pingo doce")
            return

        amount_str = parts[1]
        description = parts[2] if len(parts) > 2 else None

        # Parse and validate amount
        amount = parse_amount(amount_str)
        if amount is None:
            send_message(chat_id, MSG_INVALID_AMOUNT)
            return

        # Search for matching transactions
        matching_transactions = search_transactions(user_id, amount, description)

        if not matching_transactions:
            send_message(chat_id, MSG_NO_MATCHING_TRANSACTIONS)
            return

        # If only one match, show it with delete button
        if len(matching_transactions) == 1:
            trans = matching_transactions[0]
            msg = "🔍 Transação encontrada:\n\n"
            msg += format_transaction_details(trans)
            msg += "\n\nDeseja apagar esta transação?"

            keyboard = create_delete_keyboard(trans['PK'], trans['SK'])
            send_message(chat_id, msg, reply_markup=keyboard)

        else:
            # Multiple matches - show all with individual delete buttons
            msg = f"🔍 Encontradas {len(matching_transactions)} transações:\n\n"

            keyboard_rows = []
            for i, trans in enumerate(matching_transactions[:10], 1):  # Limit to 10
                msg += f"{i}. " + format_transaction_details(trans) + "\n\n"

                # Create button for this transaction with PK/SK
                pk_short = trans['PK'].replace('USER#', '')
                sk_short = trans['SK'].replace('TRANS#', '')
                callback_data = f"{CALLBACK_DELETE_PREFIX}{pk_short}:{sk_short}"
                keyboard_rows.append([{
                    'text': f"❌ Apagar #{i}",
                    'callback_data': callback_data
                }])

            send_message(chat_id, msg, reply_markup={'inline_keyboard': keyboard_rows})

        logger.info(f"Found {len(matching_transactions)} matching transactions for user {user_id}")

    except Exception as e:
        logger.error(f"Error handling /apagar: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)


def format_transaction_details(trans):
    """
    Format transaction details for display

    Args:
        trans (dict): Transaction item

    Returns:
        str: Formatted transaction string
    """
    trans_type = trans['type']
    amount = float(trans['amount'])
    description = trans.get('description', 'Sem descrição')
    category = trans.get('category', 'Sem categoria')
    date_str = trans.get('date_str', '')

    if trans_type == TYPE_RECEITA:
        return f"{EMOJI_INCOME} Receita: €{amount:.2f} ({date_str})"
    else:
        if category and category != 'Sem Categoria':
            return f"{EMOJI_EXPENSE} {description}: €{amount:.2f} - {category} ({date_str})"
        else:
            return f"{EMOJI_EXPENSE} {description}: €{amount:.2f} ({date_str})"


def create_delete_keyboard(pk, sk):
    """
    Create inline keyboard for delete confirmation

    Args:
        pk (str): Partition key
        sk (str): Sort key

    Returns:
        dict: Inline keyboard markup
    """
    pk_short = pk.replace('USER#', '')
    sk_short = sk.replace('TRANS#', '')
    callback_data = f"{CALLBACK_DELETE_PREFIX}{pk_short}:{sk_short}"

    keyboard = [[
        {
            'text': '❌ Sim, apagar',
            'callback_data': callback_data
        },
        {
            'text': '✖️ Cancelar',
            'callback_data': 'cancel'
        }
    ]]

    return {'inline_keyboard': keyboard}


def handle_categorias(chat_id, user_id):
    """
    Handle /categorias command - show category guide

    Args:
        chat_id (int): Chat ID
        user_id (int): User ID

    Returns:
        None
    """
    try:
        send_message(chat_id, CATEGORY_EXPLANATIONS)
        logger.info(f"Sent category guide to user {user_id}")
    except Exception as e:
        logger.error(f"Error handling /categorias: {str(e)}")
        send_message(chat_id, MSG_ERROR_OCCURRED)



