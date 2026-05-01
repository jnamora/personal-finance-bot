import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add parent dir to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock boto3 before importing db_operations
with patch('boto3.resource') as mock_dynamo:
    import db_operations
    from bot_handlers import (
        handle_despesa, 
        handle_receita, 
        handle_consulta,
        extract_date_and_description,
        parse_amount
    )
    import config

class TestBotLogic(unittest.TestCase):
    
    def setUp(self):
        # Reset mocks
        db_operations.table = MagicMock()
        self.mock_send = patch('bot_handlers.send_message').start()
        
    def tearDown(self):
        patch.stopall()

    # --- Helper Tests ---
    
    def test_parse_amount(self):
        self.assertEqual(parse_amount("10.50"), Decimal("10.50"))
        self.assertEqual(parse_amount("10,50"), Decimal("10.50"))
        self.assertEqual(parse_amount("10"), Decimal("10.00"))
        self.assertIsNone(parse_amount("abc"))
        self.assertIsNone(parse_amount("-5")) # Negative not allowed for logic

    def test_extract_date(self):
        # Case 1: Date in middle
        args = ["10", "2025-12-25", "Natal"]
        date, desc = extract_date_and_description(args)
        self.assertEqual(desc, "10 Natal") # Note: function logic expects 'args' to be REST of parts? 
        # Wait, the function in bot_handlers takes "remaining_parts" AFTER amount
        
        # Correct usage as per bot_handlers:
        # parts = ["/despesa", "10", "2025-12-25", "Natal"]
        # remaining = ["2025-12-25", "Natal"]
        
        remaining = ["2025-12-25", "Natal"]
        date, desc = extract_date_and_description(remaining)
        self.assertEqual(date.strftime("%Y-%m-%d"), "2025-12-25")
        self.assertEqual(desc, "Natal")

        # Case 2: No date
        remaining = ["Almoço", "trabalho"]
        date, desc = extract_date_and_description(remaining)
        self.assertIsNone(date)
        self.assertEqual(desc, "Almoço trabalho")
        
        # Case 3: Invalid date
        remaining = ["2025-99-99", "Teste"]
        date, desc = extract_date_and_description(remaining)
        self.assertIsNone(date)
        self.assertEqual(desc, "2025-99-99 Teste")

    # --- Command Flow Tests ---

    @patch('bot_handlers.create_transaction')
    def test_handle_despesa_flow(self, mock_create):
        # Mock create to return tokens
        mock_create.return_value = {'PK': 'USER#1', 'SK': 'TRANS#123'}
        
        # Valid usage
        handle_despesa(123, 456, "/despesa 50.00 Jantar")
        
        # Check create_transaction called correctly
        mock_create.assert_called_once()
        args = mock_create.call_args[1]
        self.assertEqual(args['amount'], Decimal("50.00"))
        self.assertEqual(args['description'], "Jantar")
        self.assertIsNone(args['custom_date'])
        
        # Check message sent
        self.mock_send.assert_called_once() 
        
    @patch('bot_handlers.create_transaction')
    def test_handle_despesa_backdated(self, mock_create):
        mock_create.return_value = {'PK': 'USER#1', 'SK': 'TRANS#123'}
        
        handle_despesa(123, 456, "/despesa 20 2025-01-01 Almoço")
        
        mock_create.assert_called_once()
        args = mock_create.call_args[1]
        self.assertEqual(args['amount'], Decimal("20.00"))
        self.assertEqual(args['custom_date'].strftime("%Y-%m-%d"), "2025-01-01")

    @patch('bot_handlers.create_transaction')
    def test_handle_receita_simplified(self, mock_create):
        # Ensure 'salário' does NOT trigger cycle logic (since we removed it)
        handle_receita(123, 456, "/receita 1000 salário")
        
        mock_create.assert_called_once()
        # Ensure no reply_markup was passed (no inline keyboard for cycle)
        call_args = self.mock_send.call_args
        self.assertNotIn('reply_markup', call_args[1] if len(call_args)>1 else {})

    # --- DB Logic Tests (Mocked Table) ---
    
    def test_calculate_summary(self):
        # Import needs to happen here or use the module ref
        from db_operations import calculate_summary
        
        transactions = [
            {'type': 'receita', 'amount': Decimal('100.00'), 'description': 'Salário'},
            {'type': 'despesa', 'amount': Decimal('20.00'), 'category': '🏠 Fixed Costs'},
            {'type': 'despesa', 'amount': Decimal('10.00'), 'category': '📈 Investments'}, # Should be treated as Investment
            {'type': 'despesa', 'amount': Decimal('5.00'), 'category': 'Sem Categoria'}
        ]
        
        summary = calculate_summary(transactions)
        
        self.assertEqual(summary['total_receitas'], Decimal('100.00'))
        self.assertEqual(summary['total_despesas'], Decimal('25.00')) # 20 + 5 
        self.assertEqual(summary['total_poupanca'], Decimal('10.00')) # Investment separate
        self.assertEqual(summary['saldo'], Decimal('65.00')) # 100 - 25 - 10
        
        # Check breakdown
        self.assertIn('🏠 Fixed Costs', summary['breakdown'])

if __name__ == '__main__':
    unittest.main()
