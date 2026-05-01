"""
AWS Lambda Handler for Telegram Finance Bot
Main entry point for API Gateway webhook
"""

import json
import logging
from bot_handlers import (
    handle_start,
    handle_despesa,
    handle_receita,
    handle_consulta,
    handle_historico,
    handle_apagar,
    handle_categorias,
    handle_categorias,
    handle_callback_query,
    send_message
)
from config import (
    CMD_START,
    CMD_DESPESA,
    CMD_RECEITA,
    CMD_CONSULTA,
    CMD_HISTORICO,
    CMD_APAGAR,
    CMD_CATEGORIAS
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Main Lambda handler function

    Processes incoming webhook requests from Telegram API Gateway

    Args:
        event (dict): API Gateway event containing Telegram update
        context (object): Lambda context object

    Returns:
        dict: Response with statusCode 200 for Telegram
    """
    try:
        # Log incoming event
        logger.info(f"Received event: {json.dumps(event)}")

        # Parse the request body
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event

        # Process Telegram update
        process_update(body)

    except Exception as e:
        # Log error but always return 200 to Telegram
        logger.error(f"Error processing update: {str(e)}", exc_info=True)

    # Always return 200 OK to Telegram
    return {
        'statusCode': 200,
        'body': json.dumps({'ok': True})
    }


def process_update(update):
    """
    Process a Telegram update

    Routes the update to appropriate handler based on type

    Args:
        update (dict): Telegram update object

    Returns:
        None
    """
    try:
        # Handle callback queries (inline keyboard responses)
        if 'callback_query' in update:
            logger.info("Processing callback query")
            handle_callback_query(update['callback_query'])
            return

        # Handle regular messages
        if 'message' in update:
            message = update['message']

            # Extract message details
            chat_id = message['chat']['id']
            user_id = message['from']['id']

            # Check if message has text
            if 'text' not in message:
                logger.info("Message has no text, ignoring")
                return

            text = message['text'].strip()

            # Log message
            logger.info(f"Processing message from user {user_id}: {text}")

            # Route to command handlers
            if text.startswith(CMD_START):
                handle_start(chat_id, user_id)

            elif text.startswith(CMD_DESPESA):
                handle_despesa(chat_id, user_id, text)

            elif text.startswith(CMD_RECEITA):
                handle_receita(chat_id, user_id, text)

            elif text.startswith(CMD_CONSULTA):
                handle_consulta(chat_id, user_id, text)

            elif text.startswith(CMD_HISTORICO):
                handle_historico(chat_id, user_id, text)

            elif text.startswith(CMD_APAGAR):
                handle_apagar(chat_id, user_id, text)

            elif text.startswith(CMD_CATEGORIAS):
                handle_categorias(chat_id, user_id)



            else:
                # Unknown command - could send help message
                logger.info(f"Unknown command: {text}")
                # Optionally send help message
                # handle_start(chat_id, user_id)

        else:
            logger.info("Update type not handled")

    except Exception as e:
        logger.error(f"Error in process_update: {str(e)}", exc_info=True)
        raise


def test_handler():
    """
    Test function for local development
    Can be used to test the handler with sample events
    """
    # Sample /start command
    test_event_start = {
        'body': json.dumps({
            'update_id': 123456789,
            'message': {
                'message_id': 1,
                'from': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'type': 'private'
                },
                'date': 1234567890,
                'text': '/start'
            }
        })
    }

    # Sample /despesa command
    test_event_despesa = {
        'body': json.dumps({
            'update_id': 123456790,
            'message': {
                'message_id': 2,
                'from': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'type': 'private'
                },
                'date': 1234567891,
                'text': '/despesa 25.50 pingo doce'
            }
        })
    }

    # Sample /receita command
    test_event_receita = {
        'body': json.dumps({
            'update_id': 123456791,
            'message': {
                'message_id': 3,
                'from': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'type': 'private'
                },
                'date': 1234567892,
                'text': '/receita 1500'
            }
        })
    }

    # Sample /consulta command
    test_event_consulta = {
        'body': json.dumps({
            'update_id': 123456792,
            'message': {
                'message_id': 4,
                'from': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'type': 'private'
                },
                'date': 1234567893,
                'text': '/consulta mes'
            }
        })
    }

    # Sample callback query
    test_event_callback = {
        'body': json.dumps({
            'update_id': 123456793,
            'callback_query': {
                'id': 'callback123',
                'from': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'message': {
                    'message_id': 2,
                    'chat': {
                        'id': 123456789,
                        'type': 'private'
                    }
                },
                'data': 'cat:uuid-1234:Alimentação'
            }
        })
    }

    print("Testing /start command...")
    result = lambda_handler(test_event_start, None)
    print(f"Result: {result}\n")

    print("Testing /despesa command...")
    result = lambda_handler(test_event_despesa, None)
    print(f"Result: {result}\n")

    print("Testing /receita command...")
    result = lambda_handler(test_event_receita, None)
    print(f"Result: {result}\n")

    print("Testing /consulta command...")
    result = lambda_handler(test_event_consulta, None)
    print(f"Result: {result}\n")

    print("Testing callback query...")
    result = lambda_handler(test_event_callback, None)
    print(f"Result: {result}\n")


# For local testing
if __name__ == '__main__':
    test_handler()
