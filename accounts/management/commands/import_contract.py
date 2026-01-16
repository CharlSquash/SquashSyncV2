from django.core.management.base import BaseCommand
from accounts.models import ContractTemplate
import os

class Command(BaseCommand):
    help = 'Import a contract template from a text file.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the .txt file containing the contract.')
        parser.add_argument('--name', type=str, help='Name for the contract template (e.g., "2026 Agreement"). Defaults to file name.')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        name = kwargs.get('name')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not name:
            name = os.path.splitext(os.path.basename(file_path))[0]

        template = ContractTemplate.objects.create(
            name=name,
            content=content,
            is_active=False  # Default to inactive, let admin enable it
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created contract template: "{template.name}"'))
