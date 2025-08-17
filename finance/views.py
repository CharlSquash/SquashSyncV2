# finance/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
import calendar

from .models import CoachSessionCompletion
from scheduling.models import Session

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser, login_url='scheduling:homepage')
def completion_report(request):
    """
    Admin report to view and confirm coach session completions for payment.
    """
    if request.method == 'POST':
        completion_id = request.POST.get('completion_id')
        action = request.POST.get('action')
        
        redirect_url = reverse('finance:completion_report')
        query_params = {}
        if request.POST.get('filter_month') and request.POST.get('filter_year'):
            query_params['month'] = request.POST.get('filter_month')
            query_params['year'] = request.POST.get('filter_year')
            redirect_url += f"?month={query_params['month']}&year={query_params['year']}"

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
        except (ValueError, CoachSessionCompletion.DoesNotExist) as e:
            messages.error(request, "Invalid request or record not found.")
        
        return redirect(redirect_url)

    today = timezone.now().date()
    
    # --- THIS IS THE FIX ---
    # Default to the current month and year instead of the previous month
    default_year = today.year
    default_month = today.month
    # --- END OF FIX ---
    
    try:
        target_year = int(request.GET.get('year', default_year))
        target_month = int(request.GET.get('month', default_month))
    except (ValueError, TypeError):
        target_year, target_month = default_year, default_month
        messages.warning(request, "Invalid filter values. Showing default period.")

    _, num_days = calendar.monthrange(target_year, target_month)
    start_date = date(target_year, target_month, 1)
    end_date = date(target_year, target_month, num_days)

    completion_records = CoachSessionCompletion.objects.filter(
        session__session_date__gte=start_date,
        session__session_date__lte=end_date
    ).select_related(
        'coach__user', 'session__school_group'
    ).order_by(
        'session__session_date', 'session__session_start_time', 'coach__user__first_name'
    )

    context = {
        'completion_records': completion_records,
        'selected_year': target_year,
        'selected_month': target_month,
        'year_choices': range(today.year + 1, today.year - 4, -1),
        'month_choices': [{'value': i, 'name': calendar.month_name[i]} for i in range(1, 13)],
        'start_date': start_date,
        'end_date': end_date,
        'page_title': f"Coach Completion Report ({start_date.strftime('%B %Y')})"
    }
    return render(request, 'finance/completion_report.html', context)