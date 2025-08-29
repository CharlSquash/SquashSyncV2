# accounts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.auth import login
from django.contrib.auth import get_user_model

from .models import Coach, CoachInvitation
from .forms import CoachInvitationForm, CoachRegistrationForm
from scheduling.models import Session 
from assessments.models import SessionAssessment, GroupAssessment
from finance.models import CoachSessionCompletion

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser, login_url='scheduling:homepage')
def coach_list(request):
    if request.method == 'POST':
        form = CoachInvitationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            invitation, created = CoachInvitation.objects.get_or_create(
                email=email, 
                defaults={'invited_by': request.user}
            )

            if not created and not invitation.is_expired():
                messages.warning(request, f"An active invitation already exists for {email}.")
            else:
                if not created: # It was expired, so create a new one
                    invitation.delete()
                    invitation = CoachInvitation.objects.create(email=email, invited_by=request.user)

                # Send invitation email
                accept_url = request.build_absolute_uri(
                    reverse('accounts:accept_invitation', args=[invitation.token])
                )
                
                html_message = render_to_string('accounts/emails/coach_invitation_email.html', {
                    'accept_url': accept_url
                })
                
                send_mail(
                    'You are invited to join SquashSync',
                    f'Please click the following link to accept the invitation: {accept_url}',
                    'noreply@squashsync.com', # Replace with your from email
                    [email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(request, f"Invitation sent to {email}.")
            
            return redirect('accounts:coach_list')
    else:
        form = CoachInvitationForm()

    coaches = Coach.objects.filter(is_active=True).select_related('user').order_by('user__first_name', 'user__last_name')
    context = {
        'coaches': coaches,
        'page_title': "Coach Profiles",
        'invitation_form': form,
    }
    return render(request, 'accounts/coach_list.html', context)

def accept_invitation(request, token):
    invitation = get_object_or_404(CoachInvitation, token=token)

    if invitation.is_accepted or invitation.is_expired():
        messages.error(request, "This invitation is no longer valid.")
        return redirect('accounts:login')

    if request.method == 'POST':
        form = CoachRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = invitation.email
            user.is_staff = True # Make them a coach
            user.save()

            # Create the corresponding Coach profile
            Coach.objects.create(
                user=user, 
                name=user.get_full_name(),
                email=user.email,
                is_active=True
            )

            invitation.is_accepted = True
            invitation.save()

            login(request, user)
            messages.success(request, "Welcome to SquashSync! Your account has been created.")
            return redirect('homepage')
    else:
        form = CoachRegistrationForm(initial={'email': invitation.email})

    return render(request, 'accounts/accept_invitation.html', {'form': form})

@login_required
def coach_profile(request, coach_id=None):
    """
    Displays a profile for a coach.
    - If coach_id is provided, an admin is viewing a specific coach's profile.
    - If coach_id is None, the logged-in coach is viewing their own profile.
    """
    target_coach = None
    
    if coach_id:
        if not request.user.is_superuser:
            messages.error(request, "You are not authorized to view this profile.")
            return redirect('scheduling:homepage')
        target_coach = get_object_or_404(Coach, pk=coach_id)
    else:
        try:
            target_coach = request.user.coach_profile
        except Coach.DoesNotExist:
            messages.error(request, "Your user account is not linked to a Coach profile.")
            return redirect('scheduling:homepage')

    # --- UPDATED DATA FETCHING LOGIC ---
    completed_sessions = CoachSessionCompletion.objects.filter(
        coach=target_coach,
        assessments_submitted=True
    ).select_related(
        'session', 'session__school_group', 'session__venue'
    ).order_by('-session__session_date', '-session__session_start_time')
    
    sessions_attended = [comp.session for comp in completed_sessions]
    
    two_weeks_ago = timezone.now().date() - timedelta(weeks=2)
    
    player_assessments_made = SessionAssessment.objects.filter(
        submitted_by=target_coach.user
    ).select_related('player', 'session').order_by('-date_recorded')

    group_assessments_made = GroupAssessment.objects.filter(
        assessing_coach=target_coach.user
    ).select_related('session__school_group').order_by('-assessment_datetime')


    context = {
        'coach': target_coach,
        'viewing_own_profile': target_coach.user == request.user,
        'sessions_attended': sessions_attended,
        'player_assessments_made': player_assessments_made,
        'group_assessments_made': group_assessments_made,
        'two_weeks_ago': two_weeks_ago,
        'page_title': f"Coach Profile: {target_coach.user.get_full_name()}"
    }
    return render(request, 'accounts/coach_profile.html', context)