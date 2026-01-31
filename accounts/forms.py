# accounts/forms.py
from django import forms
from django.utils import timezone
from datetime import date
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.urls import reverse
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Fieldset, Submit, Div, HTML

User = get_user_model()

class MonthYearFilterForm(forms.Form):
    # Dynamically create choices to stay up-to-date
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 2, current_year + 2)]
        month_choices = [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)]

        self.fields['year'] = forms.ChoiceField(choices=year_choices, initial=current_year)
        self.fields['month'] = forms.ChoiceField(choices=month_choices, initial=timezone.now().month)

class CoachInvitationForm(forms.Form):
    email = forms.EmailField(
        label="Coach's Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter coach email address'})
    )

class CoachRegistrationForm(UserCreationForm):
    phone = forms.CharField(
        max_length=20,
        required=True,
        help_text="Mobile number for contact purposes.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        # Ensure phone is ordered correctly if needed, though form rendering usually handles it.

from .models import Coach

class CoachProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        label="Phone Number",
        required=False,  # Allow saving without validation if empty
        validators=[
            RegexValidator(
                regex=r'^0\d{9}$',
                message="Please enter a valid 10-digit SA phone number (e.g., 0821234567)."
            )
        ],
        widget=forms.TextInput(attrs={'placeholder': '0821234567'})
    )

    class Meta:
        model = Coach
        fields = [
            'phone',
            'physical_address', 'id_number', 'date_of_birth',
            'car_registration_numbers', 'car_make_model', 'car_color',
            'medical_aid_name', 'medical_aid_number', 'medical_conditions',
            'emergency_contact_name', 'emergency_contact_number', 'blood_type',
            'shirt_preference', 'shirt_size',
            'occupation', 'academic_credentials', 'currently_studying',
            'highest_ranking', 'league_participation',
            'qualification_wsf_level', 'qualification_ssa_level', 'experience_notes',
            'accepts_private_coaching', 'private_coaching_preferences', 'private_coaching_area',
            'bank_name', 'account_number', 'branch_code', 'account_type'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'physical_address': forms.Textarea(attrs={'rows': 3}),
            'medical_conditions': forms.Textarea(attrs={'rows': 3}),
            'experience_notes': forms.Textarea(attrs={'rows': 3}),
            'academic_credentials': forms.Textarea(attrs={'rows': 3}),
            'private_coaching_preferences': forms.Textarea(attrs={'rows': 3}),
            'private_coaching_area': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False # Handled in template manually or we can set to True. The user said "Ensure the form renders using {% crispy form %}" so I should probably set this to True usually, but let's check the template. The template currently has <form method="post">. But the instruction says "Ensure the form renders using {% crispy form %}". So I should set form_tag = True or update template to remove <form>. Standard crispy use includes the form tag.

        # Let's clean up the layout
        self.helper.layout = Layout(
            # Group 1 (Contact)
            Fieldset(
                "Contact Details",
                Row(
                    Column('phone', css_class='form-group col-md-6 mb-0'),
                    Column('physical_address', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),
            
            # Group 2 (Personal)
            Fieldset(
                "Personal Details",
                Row(
                    Column('id_number', css_class='form-group col-md-6 mb-0'),
                    Column('date_of_birth', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),
            
            # Group 3 (Medical - Protected)
            Fieldset(
                "Medical Info (Sensitive)",
                Row(
                    Column('medical_aid_name', css_class='form-group col-md-6 mb-0'),
                    Column('medical_aid_number', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
                Row(
                    Column('blood_type', css_class='form-group col-md-6 mb-0'),
                    Column('medical_conditions', css_class='form-group col-md-6 mb-0'), # Moving this here or full width? The instruction said: Row with blood_type (Col 6). It didn't mention medical_conditions placement explicitly in group 3 but in "Big Boxes" it mentioned it. Let's put it full width or next to blood type.
                    # Instruction for Group 3: Row with medical_aid_name (Col 6) and medical_aid_number (Col 6). Row with blood_type (Col 6). 
                    # Where does medical_conditions, emergency_contact_name, emergency_contact_number go? 
                    # Ah, I missed those in the instruction detail.
                    # Wait, looking at current form fields: 'medical_conditions', 'emergency_contact_name', 'emergency_contact_number'.
                    # User instructions: 
                    # "Group 3 (Medical - Protected): Fieldset with Legend "Medical Info". Row with medical_aid_name (Col 6) and medical_aid_number (Col 6). Row with blood_type (Col 6)."
                    # It doesn't mention emergency contacts or medical conditions.
                    # I should probably include them logically.
                    # Let's put medical conditions full width under blood type?
                    # And emergency contacts in a new row or sub-group?
                    # I'll stick to the requested structure and add the missing fields logically.
                    css_class='form-row'
                ),
                 Row(
                    Column('emergency_contact_name', css_class='form-group col-md-6 mb-0'),
                    Column('emergency_contact_number', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),

            ),
            
            # Group 4 (Banking Details - Secure)
            Fieldset(
                "Banking Details",
                HTML('<div class="alert alert-info py-2"><i class="fas fa-lock me-2"></i><strong>Security Note:</strong> Your banking details are encrypted at rest. This information is only accessible by you and the administration for payment purposes.</div>'),
                Row(
                    Column('bank_name', css_class='form-group col-md-6 mb-0'),
                    Column('account_number', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
                Row(
                    Column('branch_code', css_class='form-group col-md-6 mb-0'),
                    Column('account_type', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),

            # Group 4 (Logistics)
            Fieldset(
                "Logistics & Clothing",
                Row(
                    Column('car_make_model', css_class='form-group col-md-6 mb-0'),
                    Column('car_color', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
                 Row(
                    Column('car_registration_numbers', css_class='form-group col-md-12 mb-0'), # Not mentioned in group 4 list but exists.
                    css_class='form-row'
                ),
                Row(
                    Column('shirt_preference', css_class='form-group col-md-6 mb-0'),
                    Column('shirt_size', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),

            # Group 5 (Professional)
            Fieldset(
                "Professional & Coaching",
                'experience_notes',
                'academic_credentials',
                Row(
                    Column('qualification_wsf_level', css_class='form-group col-md-6 mb-0'),
                    Column('qualification_ssa_level', css_class='form-group col-md-6 mb-0'),
                     css_class='form-row'
                ),
                 Row(
                    Column('highest_ranking', css_class='form-group col-md-6 mb-0'),
                    Column('league_participation', css_class='form-group col-md-6 mb-0'),
                     css_class='form-row'
                ),
                'occupation', 
                'currently_studying',
                Row(
                    Column('accepts_private_coaching', css_class='form-group col-md-12 mb-0'),
                     css_class='form-row'
                ),
                'private_coaching_preferences',
                'private_coaching_area'
            ),
            
            Div(
                Submit('submit', 'Save Changes', css_class='btn btn-primary'),
                HTML('<a href="{}" class="btn btn-secondary ms-2">Cancel</a>'.format(reverse('accounts:my_profile'))),
                css_class='d-flex gap-2'
            )
        )

