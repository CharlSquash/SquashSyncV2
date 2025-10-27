from django.contrib import admin
from .models import PrizeCategory, Prize, Vote, PrizeWinner # Removed Nomination import

@admin.register(PrizeCategory)
class PrizeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# NominationInline removed

class PrizeWinnerInline(admin.TabularInline):
    model = PrizeWinner
    extra = 0
    fields = ('player', 'year', 'awarded_by', 'award_date', 'final_score')
    readonly_fields = ('year',) # Year is set automatically now
    raw_id_fields = ('player', 'awarded_by')

@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'category', 'status', 'voting_start_date', 'voting_end_date')
    list_filter = ('year', 'status', 'category', 'min_grade', 'max_grade')
    search_fields = ('name', 'description', 'category__name')
    readonly_fields = ('winner',) # Display winner link, don't edit directly here
    fieldsets = (
        (None, {
            'fields': ('name', 'year', 'category', 'description')
        }),
        ('Eligibility', {
            'fields': ('min_grade', 'max_grade')
        }),
        ('Voting & Status', {
            'fields': ('status', 'voting_start_date', 'voting_end_date', 'winner') # Added winner field
        }),
    )
    inlines = [PrizeWinnerInline] # Removed NominationInline

# NominationAdmin removed

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    # --- CORRECTED LINES ---
    list_display = ('prize', 'player', 'voter', 'voted_at') # 'rank' removed
    list_filter = ('prize__year', 'prize', 'voter') # 'rank' removed
    # --- END CORRECTED LINES ---
    search_fields = ('player__first_name', 'player__last_name', 'prize__name', 'voter__username')
    readonly_fields = ('voted_at',)
    raw_id_fields = ('prize', 'player', 'voter')

@admin.register(PrizeWinner)
class PrizeWinnerAdmin(admin.ModelAdmin):
    list_display = ('player', 'prize', 'year', 'award_date', 'final_score') # Added final_score
    list_filter = ('year', 'prize__category', 'prize')
    search_fields = ('player__first_name', 'player__last_name', 'prize__name', 'year')
    raw_id_fields = ('prize', 'player', 'awarded_by')
    readonly_fields = ('year',) # Year is set automatically
    date_hierarchy = 'award_date'

