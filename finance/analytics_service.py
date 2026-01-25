from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Sum, Avg, F
import datetime
from accounts.models import Coach
from finance.models import CoachSessionCompletion, RecurringCoachAdjustment
from scheduling.models import Session, SessionCoach, ScheduledClass

def calculate_monthly_projection(year, month):
    """
    Calculates financial projections for a given month/year.
    Returns a dictionary with realised, accrued, and projected totals, plus a breakdown.
    """
    
    # 1. Setup Dates
    today = timezone.now().date()
    # If looking at a past month, 'today' for the purpose of logic is effectively the end of that month?
    # Or strict 'today'?
    # Requirement: "past sessions (date < today)", "future sessions (date >= today)"
    # If the user views a past month (e.g. last year), ALL sessions are < today. So Projected should be 0.
    # If user views future month, ALL sessions >= today. Realized/Accrued 0 (unless prepayments? No).
    
    # Date range for the requested month
    import calendar
    _, num_days = calendar.monthrange(year, month)
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)

    realized_total = Decimal('0.00')
    accrued_total = Decimal('0.00')
    projected_total = Decimal('0.00')
    
    breakdown = {
        'realized_count': 0,
        'accrued_count': 0,
        'projected_rules_count': 0,
        'projected_manual_count': 0,
        'projected_details': [] 
    }

    # --- 1. REALIZED ---
    # Sum of CoachSessionCompletion (confirmed=True)
    completions = CoachSessionCompletion.objects.filter(
        session__session_date__year=year,
        session__session_date__month=month,
        confirmed_for_payment=True
    ).select_related('coach', 'session').prefetch_related('session__sessioncoach_set')

    for comp in completions:
        # Calculate cost for this completion
        # We need the duration from SessionCoach
        session_coach = comp.session.sessioncoach_set.filter(coach=comp.coach).first()
        if session_coach and comp.coach.hourly_rate:
            duration_hours = Decimal(session_coach.coaching_duration_minutes) / Decimal('60.0')
            cost = duration_hours * comp.coach.hourly_rate
            realized_total += cost
            breakdown['realized_count'] += 1

    # Add Active RecurringCoachAdjustments
    # Recurring adjustments are monthly. 
    # Logic: If looking at current or past month, include them? 
    # Usually recurring adjustments are applied when payslips are generated. 
    # If confirmed_for_payment logic handles completions, what handles adjustments?
    # Requirement: "Sum of CoachSessionCompletion (confirmed=True) + active RecurringCoachAdjustment."
    # I will add them if they are active.
    
    recurring_adjs = RecurringCoachAdjustment.objects.filter(coach__is_active=True, is_active=True)
    # We apply these ONCE per month per coach.
    # But wait, are we calculating for specific coach or ALL coaches?
    # "Total Projected Monthly Expense" implies for the whole club/all coaches.
    recurring_total_qs = recurring_adjs.aggregate(total=Sum('amount'))
    if recurring_total_qs['total']:
        realized_total += recurring_total_qs['total']


    # --- 2. ACCRUED ---
    # Cost of past sessions (date < today) that are unconfirmed.
    # Filter sessions in the month that are < today
    
    # We query ALL sessions in the month.
    # Then split by date relative to today.
    
    sessions_in_month = Session.objects.filter(
        session_date__year=year,
        session_date__month=month,
        is_cancelled=False
    ).prefetch_related(
        'sessioncoach_set__coach', 
        'generated_from_rule',
        'coach_completions' # Reverse of CoachSessionCompletion per session? No, it's related_name='coach_completions' on Session?
        # Check finance/models.py:
        # CoachSessionCompletion: session = models.ForeignKey(..., related_name='coach_completions')
    )

    avg_coach_rate_qs = Coach.objects.filter(is_active=True, hourly_rate__isnull=False).aggregate(avg=Avg('hourly_rate'))
    avg_coach_rate = avg_coach_rate_qs['avg'] or Decimal('0.00')

    for session in sessions_in_month:
        is_past = session.session_date < today
        is_future = session.session_date >= today
        
        # Get assigned coaches
        session_coaches = session.sessioncoach_set.all()
        
        if is_past:
            # Check for EACH coach if they have a confirmed completion
            if not session_coaches:
                # If no coaches assigned in past, maybe it was a mistake or empty session. Cost = 0?
                # Or use fallback?
                # Usually past sessions should have coaches. If not, we assume 0 cost or maybe it wasn't staffed.
                pass 
            else:
                for sc in session_coaches:
                    # Check if confirmed completion exists
                    # We can check the pre-fetched 'coach_completions' on the session
                    # completion = next((c for c in session.coach_completions.all() if c.coach_id == sc.coach_id), None)
                    # Note: accessing .all() on prefetch related manager
                    
                    # Optimization:
                    # The 'coach_completions' might not be pre-fetched fully if we didn't specify it in prefetch_related correctly.
                    # Let's trust we iterate.
                    
                    # We need to see if THIS coach has a confirmed completion for THIS session.
                    has_confirmed = CoachSessionCompletion.objects.filter(
                        session=session, 
                        coach=sc.coach, 
                        confirmed_for_payment=True
                    ).exists()
                    
                    if not has_confirmed:
                        # It is Accrued
                        if sc.coach.hourly_rate:
                            duration_hours = Decimal(sc.coaching_duration_minutes) / Decimal('60.0')
                            cost = duration_hours * sc.coach.hourly_rate
                            accrued_total += cost
                            breakdown['accrued_count'] += 1
                        
        elif is_future:
            # --- 3. PROJECTED ---
            # Future sessions (date >= today)
            
            # Logic: If rule -> Historical Average.
            if session.generated_from_rule:
                # Calculate rule's historical average cost
                # "avg cost of last 5 finished sessions of that rule"
                rule = session.generated_from_rule
                
                # We need to calculate this efficiently. 
                # Doing this inside a loop might be N+1 query heavy. 
                # But for a single month view (max ~100-200 sessions), it might be acceptable.
                # Optimization: Cache rule averages? 
                
                last_5_sessions = Session.objects.filter(
                    generated_from_rule=rule,
                    status='finished',
                    session_date__lt=today
                ).exclude(id=session.id).order_by('-session_date')[:5]
                
                costs = []
                for hist_sess in last_5_sessions:
                    # Calculate total cost for this historic session
                    sess_cost = Decimal('0.00')
                    for h_sc in hist_sess.sessioncoach_set.all():
                         if h_sc.coach.hourly_rate:
                            h_dur = Decimal(h_sc.coaching_duration_minutes) / Decimal('60.0')
                            sess_cost += h_dur * h_sc.coach.hourly_rate
                    if sess_cost > 0:
                        costs.append(sess_cost)
                
                if costs:
                    avg_cost = sum(costs) / len(costs)
                    projected_total += avg_cost
                    breakdown['projected_rules_count'] += 1
                    # breakdown['projected_details'].append(f"Rule {rule.id}: Avg {avg_cost:.2f}")
                else:
                    # Fallback: planned_duration * Average Coach Rate
                    duration_hours = Decimal(session.planned_duration_minutes) / Decimal('60.0')
                    est_cost = duration_hours * avg_coach_rate
                    projected_total += est_cost
                    breakdown['projected_rules_count'] += 1 # Still counted as rule-based, just fallback used
            else:
                # Manual session (future)
                # If coaches assigned, use them?
                # Or use fallback?
                # "Fallback: If no history, use planned_duration * Average Coach Rate."
                # I'll stick to assigned coaches if available, else fallback.
                
                session_cost = Decimal('0.00')
                if session_coaches:
                    for sc in session_coaches:
                        if sc.coach.hourly_rate:
                            dur = Decimal(sc.coaching_duration_minutes) / Decimal('60.0')
                            session_cost += dur * sc.coach.hourly_rate
                else:
                    duration_hours = Decimal(session.planned_duration_minutes) / Decimal('60.0')
                    session_cost = duration_hours * avg_coach_rate
                
                projected_total += session_cost
                breakdown['projected_manual_count'] += 1

    return {
        'realized_total': realized_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'accrued_total': accrued_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'projected_total': projected_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'grand_total': (realized_total + accrued_total + projected_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'breakdown': breakdown
    }
