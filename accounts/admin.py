# accounts/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Coach, CoachInvitation

from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib import messages
# We don't need timezone here anymore, the form handles it

from finance.forms import PayslipGenerationForm
from finance.payslip_services import generate_payslip_for_single_coach # Using the single coach function

@admin.register(Coach)
class CoachAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'hourly_rate')
    list_filter = ('is_active',)
    search_fields = ('name', 'user__username')
    
    @admin.action(description="Generate Payslips for selected coaches")
    def generate_payslips(self, request, queryset):
        
        # This 'if' block handles the form SUBMISSION from the intermediate page
        if 'process_payslips' in request.POST:
            form = PayslipGenerationForm(request.POST) # Bind to the submitted data
            
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
            
            # If form is invalid, it will fall through and re-render with errors
        
        # This 'else' block handles the INITIAL display of the form
        # (which is triggered by the POST from the changelist)
        else:
            # Create a new, unbound form. The form's __init__ will set the defaults.
            form = PayslipGenerationForm() 
        
        # *** THE FIX IS HERE ***
        # We must add 'opts' to the context so the admin templates can build the breadcrumbs.
        context = {
            **self.admin_site.each_context(request),
            'title': "Generate Payslips",
            'opts': self.model._meta,  # This provides app_label, model_name, etc.
            'queryset': queryset,
            'form': form, # Pass the correct form instance
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

@admin.register(CoachInvitation)
class CoachInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_accepted', 'expires_at', 'invited_by')
    list_filter = ('is_accepted', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('token', 'created_at', 'expires_at')

from .models import ContractTemplate, CoachContract

@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'content')

@admin.register(CoachContract)
class CoachContractAdmin(admin.ModelAdmin):
    list_display = ('coach', 'template', 'status', 'date_signed', 'created_at')
    list_filter = ('status', 'template', 'date_signed')
    search_fields = ('coach__name', 'coach__user__email', 'customized_content')
    readonly_fields = ('date_signed', 'ip_address', 'created_at')
    actions = ['send_to_coach']

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != CoachContract.Status.DRAFT:
            return self.readonly_fields + ('customized_content', 'template', 'coach')
        return self.readonly_fields

    @admin.action(description="Send to Coach (Make visible for signing)")
    def send_to_coach(self, request, queryset):
        count = queryset.update(status=CoachContract.Status.AWAITING_SIGNATURE)
        self.message_user(request, f"{count} contract(s) sent to coach.", messages.SUCCESS)

