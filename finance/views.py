# finance/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
import calendar

# Import models from their correct new app locations
from .models import CoachSessionCompletion
from scheduling.models import Session
from accounts.models import Coach
from .payslip_services import get_payslip_data_for_coach


def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser, login_url='scheduling:homepage')
def completion_report(request):
    """
    Admin report to view and confirm coach session completions for payment.
    This view now automatically creates completion records for past, finished sessions.
    """
    if request.method == 'POST':
        completion_id = request.POST.get('completion_id')
        action = request.POST.get('action')
        
        redirect_url = reverse('finance:completion_report')
        query_params = {}
        if request.POST.get('filter_month') and request.POST.get('filter_year'):
            query_params['month'] = request.POST.get('filter_month')
            query_params['year'] = request.POST.get('filter_year')
        if request.POST.get('filter_coach'):
            query_params['coach'] = request.POST.get('filter_coach')
        
        if query_params:
            redirect_url += '?' + '&'.join([f'{k}={v}' for k, v in query_params.items()])

        try:
            completion_record = get_object_or_404(CoachSessionCompletion, pk=int(completion_id))
            if action == 'confirm':
                completion_record.confirmed_for_payment = True
                messages.success(request, f"Payment confirmed for {completion_record.coach.user.get_full_name()} for session on {completion_record.session.session_date.strftime('%d %b %Y')}.")
            elif action == 'unconfirm':
                completion_record.confirmed_for_payment = False
                messages.warning(request, f"Payment confirmation removed for {completion_record.coach.user.get_full_name()} for session on {completion_record.session.session_date.strftime('%d %b %Y')}.")
            else:
                messages.error(request, "Invalid action specified.")
                return redirect(redirect_url)
            
            completion_record.save(update_fields=['confirmed_for_payment'])
        except (ValueError, CoachSessionCompletion.DoesNotExist):
            messages.error(request, "Invalid request or record not found.")
        
        return redirect(redirect_url)

    # --- GET Request Logic ---
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

    # --- REVISED: Auto-create completion records ---
    # 1. Fetch all potentially relevant sessions for the period from the database.
    sessions_in_period = Session.objects.filter(
        session_date__gte=start_date,
        session_date__lte=end_date,
        is_cancelled=False
    ).prefetch_related('coaches_attending')

    # 2. In Python, filter this list to find sessions whose scheduled end time has passed.
    finished_sessions_in_period = []
    for session in sessions_in_period:
        # The session.end_datetime property calculates the scheduled end time
        if session.end_datetime and session.end_datetime < now_aware:
            finished_sessions_in_period.append(session)

    # 3. Create the completion records for the truly finished sessions.
    for session in finished_sessions_in_period:
        for coach in session.coaches_attending.all():
            CoachSessionCompletion.objects.get_or_create(
                coach=coach,
                session=session
            )
    # --- END REVISION ---

    completion_records = CoachSessionCompletion.objects.filter(
        session__session_date__gte=start_date,
        session__session_date__lte=end_date
    ).select_related(
        'coach__user', 'session__school_group'
    ).order_by(
        'session__session_date', 'session__session_start_time', 'coach__user__first_name'
    )

    payslip_data = None
    if target_coach_id:
        completion_records = completion_records.filter(coach__id=target_coach_id)
        payslip_data = get_payslip_data_for_coach(int(target_coach_id), target_year, target_month)

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
