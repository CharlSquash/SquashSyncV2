
# accounts/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Coach

from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages

from finance.forms import PayslipGenerationForm
from finance.payslip_services import generate_payslip_for_single_coach # Using the single coach function

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'hourly_rate')
    list_filter = ('is_active',)
    search_fields = ('name', 'user__username')
    
    @admin.action(description="Generate Payslips for selected coaches")
    def generate_payslips(self, request, queryset):
        form = PayslipGenerationForm(request.POST or None)

        if 'process_payslips' in request.POST:
            if form.is_valid():
                year = int(form.cleaned_data['year'])
                month = int(form.cleaned_data['month'])
                force_regeneration = form.cleaned_data['force_regeneration']
                
                generated_count = 0
                error_count = 0
                skipped_count = 0
                
                for coach in queryset:
                    result = generate_payslip_for_single_coach(
                        coach_id=coach.id,
                        year=year,
                        month=month,
                        generating_user_id=request.user.id,
                        force_regeneration=force_regeneration
                    )
                    if result['status'] == 'success':
                        generated_count += 1
                        messages.success(request, result['message'])
                    elif result['status'] == 'error':
                        error_count += 1
                        messages.error(request, result['message'])
                    else: # 'skipped'
                        skipped_count += 1
                        messages.warning(request, result['message'])

                summary = f"Processed {queryset.count()} coaches. Generated: {generated_count}, Skipped: {skipped_count}, Errors: {error_count}."
                self.message_user(request, summary, messages.INFO)
                
                return HttpResponseRedirect(request.get_full_path())
        
        # *** THE FIX IS HERE ***
        # We must add 'opts' to the context so the admin templates can build the breadcrumbs.
        context = {
            **self.admin_site.each_context(request),
            'title': "Generate Payslips",
            'opts': self.model._meta,  # This provides app_label, model_name, etc.
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/accounts/coach/generate_payslips_form.html', context)

    actions = ['generate_payslips']
    

@admin.action(description="Generate Payslips for selected coaches")
def generate_payslips(modeladmin, request, queryset):
    form = PayslipGenerationForm(request.POST or None)

    if 'process_payslips' in request.POST:
        if form.is_valid():
            year = int(form.cleaned_data['year'])
            month = int(form.cleaned_data['month'])
            force_regeneration = form.cleaned_data['force_regeneration']
            
            generated_count = 0
            error_count = 0
            
            for coach in queryset:
                result = generate_payslip_for_single_coach(
                    coach_id=coach.id,
                    year=year,
                    month=month,
                    generating_user_id=request.user.id,
                    force_regeneration=force_regeneration
                )
                if result['status'] == 'success':
                    generated_count += 1
                    messages.success(request, result['message'])
                elif result['status'] == 'error':
                    error_count += 1
                    messages.error(request, result['message'])
                else: # skipped
                    messages.info(request, result['message'])

            modeladmin.message_user(request, f"Processed {queryset.count()} coaches. Generated: {generated_count}, Errors: {error_count}.")
            return HttpResponseRedirect(request.get_full_path())

    context = {
        **modeladmin.admin_site.each_context(request),
        'title': "Generate Payslips",
        'queryset': queryset,
        'form': form,
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
    }
    # Important: The template path matches the app and model of the admin page it's on
    return render(request, 'admin/accounts/coach/generate_payslips_form.html', context)

