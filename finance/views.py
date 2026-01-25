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
from django.views.decorators.http import require_POST, require_http_methods
import json

# Import models from their correct new app locations
from .models import CoachSessionCompletion, RecurringCoachAdjustment # Import new model
from scheduling.models import Session, SessionCoach
from accounts.models import Coach
from .payslip_services import get_payslip_data_for_coach
from .forms import RecurringCoachAdjustmentForm # Import new form
from .analytics_service import calculate_monthly_projection



def is_superuser(user):
    return user.is_superuser

# --- NEW HELPER FUNCTION ---
def _get_updated_finance_context(coach_id, year, month):
    """
    Helper to get updated payslip data and render the partials.
    """
    payslip_data = get_payslip_data_for_coach(coach_id, year, month)
    recurring_adjustments = RecurringCoachAdjustment.objects.filter(coach_id=coach_id).order_by('-is_active', 'description')
    adjustments_form = RecurringCoachAdjustmentForm() # A fresh form

    payment_summary_html = render_to_string(
        'finance/partials/payment_summary.html',
        {
            'payslip_data': payslip_data,
            'selected_coach_id': coach_id
        }
    )
    
    adjustments_list_html = render_to_string(
        'finance/partials/adjustments_list.html',
        {
            'recurring_adjustments': recurring_adjustments,
            'adjustments_form': adjustments_form,
            'selected_coach_id': coach_id
        }
    )
    
    return {
        'payment_summary_html': payment_summary_html,
        'adjustments_list_html': adjustments_list_html,
    }

@login_required
@require_POST
@user_passes_test(is_superuser)
def toggle_confirmation_ajax(request, completion_id):
    """
    Handles the AJAX request to confirm or un-confirm a payment.
    Now also returns updated payslip and adjustments data.
    """
    try:
        completion = get_object_or_404(CoachSessionCompletion.objects.select_related('coach', 'session'), pk=completion_id)
        completion.confirmed_for_payment = not completion.confirmed_for_payment
        completion.save(update_fields=['confirmed_for_payment'])
        
        context_html = _get_updated_finance_context(
            completion.coach.id,
            completion.session.session_date.year,
            completion.session.session_date.month
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Status updated.',
            'new_state': completion.confirmed_for_payment,
            'payment_summary_html': context_html['payment_summary_html'],
            'adjustments_list_html': context_html['adjustments_list_html']
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
@user_passes_test(is_superuser)
def update_duration_ajax(request, session_coach_id):
    """
    Handles the AJAX request to update a coach's session duration.
    Now also returns updated payslip and adjustments data.
    """
    try:
        data = json.loads(request.body)
        duration = int(data.get('duration'))
        
        session_coach = get_object_or_404(SessionCoach.objects.select_related('coach', 'session'), pk=session_coach_id)
        session_coach.coaching_duration_minutes = duration
        session_coach.save(update_fields=['coaching_duration_minutes'])
        
        context_html = _get_updated_finance_context(
            session_coach.coach.id,
            session_coach.session.session_date.year,
            session_coach.session.session_date.month
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Duration updated for {session_coach.coach.name}.',
            'payment_summary_html': context_html['payment_summary_html'],
            'adjustments_list_html': context_html['adjustments_list_html']
        })
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid data provided.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# --- NEW AJAX VIEW ---
@login_required
@require_POST
@user_passes_test(is_superuser)
def manage_adjustment_ajax(request, adj_id=None):
    """
    Handles creating or updating a RecurringCoachAdjustment via AJAX.
    """
    coach_id = request.POST.get('coach_id')
    year = int(request.POST.get('year'))
    month = int(request.POST.get('month'))
    
    if not coach_id:
        return JsonResponse({'status': 'error', 'message': 'Coach ID is missing.'}, status=400)

    instance = None
    if adj_id:
        instance = get_object_or_404(RecurringCoachAdjustment, pk=adj_id, coach_id=coach_id)
    
    form = RecurringCoachAdjustmentForm(request.POST, instance=instance)
    
    if form.is_valid():
        adj = form.save(commit=False)
        if not instance: # If it's a new one, assign the coach
            adj.coach_id = coach_id
        adj.save()
        
        context_html = _get_updated_finance_context(coach_id, year, month)
        return JsonResponse({
            'status': 'success',
            'message': 'Adjustment saved.',
            'payment_summary_html': context_html['payment_summary_html'],
            'adjustments_list_html': context_html['adjustments_list_html']
        })
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid form data.', 'errors': form.errors}, status=400)

# --- NEW AJAX VIEW ---
@login_required
@require_http_methods(["DELETE"]) # Use DELETE method for deletion
@user_passes_test(is_superuser)
def delete_adjustment_ajax(request, adj_id):
    """
    Handles deleting a RecurringCoachAdjustment via AJAX.
    """
    try:
        adj = get_object_or_404(RecurringCoachAdjustment, pk=adj_id)
        coach_id = adj.coach_id
        
        # Get year/month from the request body to ensure context is correct
        data = json.loads(request.body)
        year = int(data.get('year'))
        month = int(data.get('month'))
        
        adj.delete()
        
        context_html = _get_updated_finance_context(coach_id, year, month)
        return JsonResponse({
            'status': 'success',
            'message': 'Adjustment deleted.',
            'payment_summary_html': context_html['payment_summary_html'],
            'adjustments_list_html': context_html['adjustments_list_html']
        })
    except json.JSONDecodeError:
         return JsonResponse({'status': 'error', 'message': 'Invalid request data.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
@user_passes_test(is_superuser)
def toggle_adjustment_ajax(request, adj_id):
    """
    Handles activating or deactivating a RecurringCoachAdjustment via AJAX.
    """
    try:
        adj = get_object_or_404(RecurringCoachAdjustment, pk=adj_id)
        adj.is_active = not adj.is_active
        adj.save(update_fields=['is_active'])
        
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))
        
        context_html = _get_updated_finance_context(adj.coach_id, year, month)
        return JsonResponse({
            'status': 'success',
            'message': 'Adjustment status toggled.',
            'payment_summary_html': context_html['payment_summary_html'],
            'adjustments_list_html': context_html['adjustments_list_html']
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@user_passes_test(is_superuser)
def financial_projection_ajax(request):
    """
    Returns the HTML for the Financial Analytics modal.
    """
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
        
        data = calculate_monthly_projection(year, month)
        
        html = render_to_string('finance/partials/financial_projection_modal.html', {
            'data': data,
            'year': year,
            'month': month
        })
        
        return JsonResponse({
            'status': 'success',
            'html': html
        })
    except (ValueError, TypeError):
         return JsonResponse({'status': 'error', 'message': 'Invalid year or month.'}, status=400)
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

    # Optimization: Bulk create CoachSessionCompletion records
    # 1. Get all session IDs
    finished_session_ids = [s.id for s in finished_sessions_in_period]

    # 2. Fetch existing completions for these sessions to avoid duplicates
    existing_pairs = set(
        CoachSessionCompletion.objects.filter(
            session_id__in=finished_session_ids
        ).values_list('coach_id', 'session_id')
    )

    # 3. Prepare new objects
    new_completions = []
    for session in finished_sessions_in_period:
        # session.sessioncoach_set.all() is already prefetched with 'sessioncoach_set__coach'
        for session_coach in session.sessioncoach_set.all():
            if (session_coach.coach_id, session.id) not in existing_pairs:
                new_completions.append(
                    CoachSessionCompletion(
                        coach=session_coach.coach,
                        session=session
                    )
                )
                # Add to set to prevent duplicates if multiple identical session_coaches exist
                existing_pairs.add((session_coach.coach_id, session.id))

    # 4. Bulk create
    if new_completions:
        CoachSessionCompletion.objects.bulk_create(new_completions)

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
    recurring_adjustments = None
    adjustments_form = None
    
    if target_coach_id:
        completion_records = completion_records.filter(coach__id=target_coach_id)
        payslip_data = get_payslip_data_for_coach(int(target_coach_id), target_year, target_month)
        recurring_adjustments = RecurringCoachAdjustment.objects.filter(coach_id=target_coach_id).order_by('-is_active', 'description')
        adjustments_form = RecurringCoachAdjustmentForm()


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
        'recurring_adjustments': recurring_adjustments, # NEW
        'adjustments_form': adjustments_form, # NEW
    }
    return render(request, 'finance/completion_report.html', context)
