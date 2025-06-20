# finance/payslip_services.py

from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from weasyprint import HTML
import calendar
from datetime import date

# Import models from their new locations
from .models import Payslip, CoachSessionCompletion
from accounts.models import Coach
from scheduling.models import Session
from django.contrib.auth import get_user_model

User = get_user_model()

def generate_payslip_for_single_coach(coach_id: int, year: int, month: int, generating_user_id: int = None, force_regeneration: bool = False):
    """
    Generates a PDF payslip for a single coach for a specific month and year.
    """
    try:
        coach = Coach.objects.get(pk=coach_id)
    except Coach.DoesNotExist:
        return {'status': 'error', 'message': f"Coach with ID {coach_id} not found."}

    # Check for existing payslip and handle force_regeneration
    existing_payslip = Payslip.objects.filter(coach=coach, year=year, month=month).first()
    if existing_payslip and not force_regeneration:
        return {'status': 'skipped', 'message': f"Payslip for {coach.name} for {month}/{year} already exists."}
    elif existing_payslip and force_regeneration:
        existing_payslip.delete()

    # Find all confirmed, non-cancelled sessions for the coach in the given period
    _, num_days = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)

    completed_sessions = CoachSessionCompletion.objects.filter(
        coach=coach,
        session__session_date__gte=start_date,
        session__session_date__lte=end_date,
        session__is_cancelled=False,
        confirmed_for_payment=True
    ).select_related('session', 'session__venue')

    if not completed_sessions.exists():
        return {'status': 'skipped', 'message': f"No confirmed sessions found for {coach.name} for {month}/{year}."}

    line_items = []
    total_amount = 0
    bonus_amount = settings.BONUS_SESSION_AMOUNT
    bonus_time = settings.BONUS_SESSION_START_TIME

    for completion in completed_sessions:
        session = completion.session
        rate = coach.hourly_rate or 0
        hours = session.planned_duration_minutes / 60
        session_pay = rate * decimal(hours)
        line_items.append({'session': session, 'pay': session_pay})
        total_amount += session_pay

        # Bonus calculation
        if session.session_start_time == bonus_time:
            line_items.append({'session': session, 'is_bonus': True, 'pay': bonus_amount})
            total_amount += bonus_amount

    # Get generating user instance
    generating_user = User.objects.get(pk=generating_user_id) if generating_user_id else None

    # Render PDF from template
    html_string = render_to_string('finance/payslip_template.html', {
        'coach': coach,
        'month_name': calendar.month_name[month],
        'year': year,
        'line_items': line_items,
        'total_amount': total_amount,
    })
    pdf_file = HTML(string=html_string).write_pdf()

    # Create and save Payslip model instance
    payslip = Payslip.objects.create(
        coach=coach,
        month=month,
        year=year,
        total_amount=total_amount,
        generated_by=generating_user
    )
    payslip_filename = f'payslip_{coach.name.replace(" ", "_")}_{year}_{month:02d}.pdf'
    payslip.file.save(payslip_filename, ContentFile(pdf_file), save=True)

    return {'status': 'success', 'message': f"Payslip for {coach.name} for {month}/{year} generated successfully."}