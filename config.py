"""
Configuration file for Telegram Finance Bot
Contains constants, categories, and configuration settings
"""

import os

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'finance-transactions')

# Telegram API Configuration
TELEGRAM_API_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# DynamoDB Key Prefixes
USER_PREFIX = "USER#"
TRANSACTION_PREFIX = "TRANS#"

# Transaction Types
TYPE_DESPESA = "despesa"
TYPE_RECEITA = "receita"

# Categories (Portuguese - Portugal)
# Organized by: Fixed Expenses, Variable Expenses, Optional, Savings, Other
CATEGORIES = [
    "🏠 Fixed Costs",
    "💖 Mimos",
    "📈 Investments"
]

# Category explanations for users
CATEGORY_EXPLANATIONS = """📋 Guia de Categorias

🏠 **Fixed Costs** (Essenciais)
  Habitação, Contas, Transportes, Alimentação, Saúde

💖 **Mimos** (Opcionais)
  Lazer, Vestuário, Entretenimento, Presentes, Outros

📈 **Investments** (Futuro)
  Poupança, Investimentos, Fundos"""

# Emojis for responses
EMOJI_EXPENSE = "🔴"  # Red circle for expenses
EMOJI_INCOME = "🟢"   # Green circle for income
EMOJI_SAVINGS = "🟡"  # Yellow circle for savings/investments
EMOJI_STATS = "📊"
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_INFO = "ℹ️"
EMOJI_CALENDAR = "📅"

# Command patterns
CMD_DESPESA = "/despesa"
CMD_RECEITA = "/receita"
CMD_CONSULTA = "/consulta"
CMD_START = "/start"
CMD_HISTORICO = "/historico"
CMD_APAGAR = "/apagar"
CMD_CATEGORIAS = "/categorias"

# Callback data patterns
CALLBACK_CATEGORY_PREFIX = "cat:"
CALLBACK_DELETE_PREFIX = "del:"

# Messages (Portuguese - Portugal)
MSG_WELCOME = f"""{EMOJI_INFO} Bem-vindo ao Bot de Finanças Pessoais!

Comandos disponíveis:

📂 /categorias
   Ver guia de categorias

{EMOJI_EXPENSE} /despesa <valor> <descrição>
   Registar uma despesa
   Exemplo: /despesa 25.50 pingo doce

{EMOJI_INCOME} /receita <valor> <descrição>
   Registar uma receita
   Exemplo: /receita 1500 salário

{EMOJI_STATS} /consulta <período>
   Consultar resumo financeiro
   Períodos: mes, ano, YYYY-MM
   Exemplos: /consulta mes, /consulta 2025-10

📋 /historico [N]
   Ver últimas transações (padrão: 5)
   Exemplo: /historico 20

{EMOJI_ERROR} /apagar <valor> [descrição]
   Apagar uma transação
   Exemplos: /apagar 25.50 ou /apagar 25.50 pingo doce

Use os comandos acima para gerir as suas finanças!"""

MSG_INVALID_AMOUNT = f"{EMOJI_ERROR} Valor inválido. Use números positivos (ex: 25.50 ou 25,50)"
MSG_MISSING_DESCRIPTION = f"{EMOJI_ERROR} Descrição é obrigatória. Exemplo: /despesa 25.50 pingo doce"
MSG_INVALID_PERIOD = f"{EMOJI_ERROR} Período inválido. Use: mes, ano ou YYYY-MM (ex: 2025-10)"
MSG_NO_TRANSACTIONS = f"{EMOJI_INFO} Não há transações para o período selecionado."
MSG_ERROR_OCCURRED = f"{EMOJI_ERROR} Ocorreu um erro. Tente novamente."
MSG_CATEGORY_UPDATED = f"{EMOJI_SUCCESS} Categoria atualizada!"
MSG_TRANSACTION_DELETED = f"{EMOJI_SUCCESS} Transação apagada!"
MSG_NO_MATCHING_TRANSACTIONS = f"{EMOJI_INFO} Não foram encontradas transações com esse valor e descrição."

def get_expense_saved_message(amount, description):
    """Generate message for saved expense"""
    return f"{EMOJI_SUCCESS} Despesa registada: €{amount:.2f} - {description}\n\nSelecione a categoria:"

def get_income_saved_message(amount, description):
    """Generate message for saved income"""
    return f"{EMOJI_SUCCESS} Receita registada: €{amount:.2f} - {description}"

def get_summary_message(period_name, total_receitas, total_despesas, saldo, count, breakdown, transactions_by_category=None, receita_transactions=None, total_poupanca=None, poupanca_transactions=None):
    """Generate summary message with individual transactions"""
    msg = f"Resumo Financeiro - {period_name}\n\n"
    msg += f"{EMOJI_INCOME} Receitas: €{total_receitas:.2f}\n"
    msg += f"{EMOJI_EXPENSE} Despesas: €{total_despesas:.2f}\n"

    # Show Investimentos separately
    if total_poupanca and total_poupanca > 0:
        msg += f"{EMOJI_SAVINGS} Investimentos: €{total_poupanca:.2f}\n"

    msg += f"Saldo: €{saldo:.2f}\n"

    # Separator line
    msg += f"\n━━━━━━━━━━━━━━━━\n"

    # Show receita breakdown
    if receita_transactions and len(receita_transactions) > 0:
        msg += f"{EMOJI_INCOME} Detalhes das Receitas:\n"
        for trans in receita_transactions:
            msg += f"  - {trans['description']}: €{trans['amount']:.2f}\n"

    # Show investimentos breakdown
    if poupanca_transactions and len(poupanca_transactions) > 0:
        msg += f"\n{EMOJI_SAVINGS} Investimentos:\n"
        for trans in poupanca_transactions:
            msg += f"  - {trans['description']}: €{trans['amount']:.2f}\n"

    # Show despesa breakdown by category
    if breakdown:
        msg += f"\n{EMOJI_EXPENSE} Detalhes das Despesas:\n"
        for category, amount in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
            if amount > 0:
                msg += f"      {category}: €{amount:.2f}\n"

                # Add individual transactions if available
                if transactions_by_category and category in transactions_by_category:
                    for trans in transactions_by_category[category]:
                        msg += f"           - {trans['description']}: €{trans['amount']:.2f}\n"

    return msg
