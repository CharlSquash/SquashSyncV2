# finance/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import date
import calendar
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
import json

# Import models from their correct new app locations
from .models import CoachSessionCompletion
from scheduling.models import Session, SessionCoach
from accounts.models import Coach
from .payslip_services import get_payslip_data_for_coach


def is_superuser(user):
    return user.is_superuser

@login_required
@require_POST
@user_passes_test(is_superuser)
def toggle_confirmation_ajax(request, completion_id):
    """
    Handles the AJAX request to confirm or un-confirm a payment.
    Now also returns updated payslip data.
    """
    try:
        completion = get_object_or_404(CoachSessionCompletion.objects.select_related('coach', 'session'), pk=completion_id)
        completion.confirmed_for_payment = not completion.confirmed_for_payment
        completion.save(update_fields=['confirmed_for_payment'])
        
        payslip_data = get_payslip_data_for_coach(
            coach_id=completion.coach.id,
            year=completion.session.session_date.year,
            month=completion.session.session_date.month
        )
        
        payment_summary_html = render_to_string(
            'finance/partials/payment_summary.html',
            {
                'payslip_data': payslip_data,
                'selected_coach_id': completion.coach.id # Needed for the partial template's logic
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Status updated.',
            'new_state': completion.confirmed_for_payment,
            'payment_summary_html': payment_summary_html
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
@user_passes_test(is_superuser)
def update_duration_ajax(request, session_coach_id):
    """
    Handles the AJAX request to update a coach's session duration.
    """
    try:
        data = json.loads(request.body)
        duration = int(data.get('duration'))
        
        session_coach = get_object_or_404(SessionCoach.objects.select_related('coach', 'session'), pk=session_coach_id)
        session_coach.coaching_duration_minutes = duration
        session_coach.save(update_fields=['coaching_duration_minutes'])
        
        payslip_data = get_payslip_data_for_coach(
            coach_id=session_coach.coach.id,
            year=session_coach.session.session_date.year,
            month=session_coach.session.session_date.month
        )
        
        payment_summary_html = render_to_string(
            'finance/partials/payment_summary.html',
            {
                'payslip_data': payslip_data,
                'selected_coach_id': session_coach.coach.id
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Duration updated for {session_coach.coach.name}.',
            'payment_summary_html': payment_summary_html
        })
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data provided.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_superuser, login_url='scheduling:homepage')
def completion_report(request):
    """
    Admin report to view coach session completions.
    All updates are now handled via AJAX.
    """
    # GET Request Logic
    today = timezone.now().date()
    now_aware = timezone.now()
    default_year = today.year
    default_month = today.month
    
    try:
        target_year = int(request.GET.get('year', default_year))
        target_month = int(request.GET.get('month', default_month))
        target_coach_id = request.GET.get('coach')
    except (ValueError, TypeError):
        target_year, target_month = default_year, default_month
        target_coach_id = None
        messages.warning(request, "Invalid filter values. Showing default period.")

    _, num_days = calendar.monthrange(target_year, target_month)
    start_date = date(target_year, target_month, 1)
    end_date = date(target_year, target_month, num_days)

    finished_sessions_in_period_qs = Session.objects.filter(
        session_date__range=[start_date, end_date],
        is_cancelled=False,
    ).exclude(
        session_date__gt=today
    ).prefetch_related('sessioncoach_set__coach')
    
    finished_sessions_in_period = [
        s for s in finished_sessions_in_period_qs
        if s.session_date < today or (s.session_date == today and s.session_start_time < now_aware.time())
    ]

    for session in finished_sessions_in_period:
        for session_coach in session.sessioncoach_set.all():
            CoachSessionCompletion.objects.get_or_create(
                coach=session_coach.coach,
                session=session
            )

    completion_records = CoachSessionCompletion.objects.filter(
        session__session_date__gte=start_date,
        session__session_date__lte=end_date
    ).select_related(
        'coach__user', 'session__school_group'
    ).prefetch_related(
        'session__sessioncoach_set'
    ).order_by(
        'session__session_date', 'session__session_start_time', 'coach__name'
    )

    payslip_data = None
    if target_coach_id:
        completion_records = completion_records.filter(coach__id=target_coach_id)
        payslip_data = get_payslip_data_for_coach(int(target_coach_id), target_year, target_month)

    for record in completion_records:
        record.session_coach = next((sc for sc in record.session.sessioncoach_set.all() if sc.coach_id == record.coach_id), None)

    all_coaches = Coach.objects.filter(is_active=True).select_related('user')

    context = {
        'completion_records': completion_records,
        'selected_year': target_year,
        'selected_month': target_month,
        'selected_coach_id': int(target_coach_id) if target_coach_id else None,
        'all_coaches': all_coaches,
        'year_choices': range(today.year + 1, today.year - 4, -1),
        'month_choices': [{'value': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
        'start_date': start_date,
        'end_date': end_date,
        'page_title': f"Coach Completion Report ({start_date.strftime('%B %Y')})",
        'payslip_data': payslip_data,
    }
    return render(request, 'finance/completion_report.html', context)

