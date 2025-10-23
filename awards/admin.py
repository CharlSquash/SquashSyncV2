# awards/admin.py
from django.contrib import admin
from .models import PrizeCategory, Prize, Nomination, Vote, PrizeWinner

@admin.register(PrizeCategory)
class PrizeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

class NominationInline(admin.TabularInline):
    model = Nomination
    extra = 0 # Don't show empty nomination forms by default
    fields = ('player', 'justification', 'total_vote_score')
    readonly_fields = ('total_vote_score',) # Score is calculated, not edited directly
    raw_id_fields = ('player',) # Use a search popup for players
    # You might want to limit the queryset for 'player' based on prize eligibility later

class PrizeWinnerInline(admin.TabularInline):
    model = PrizeWinner
    extra = 0
    fields = ('player', 'year', 'awarded_by', 'award_date')
    raw_id_fields = ('player', 'awarded_by')

@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'category', 'status', 'voting_start_date', 'voting_end_date')
    list_filter = ('year', 'status', 'category', 'min_grade', 'max_grade')
    search_fields = ('name', 'description', 'category__name')
    fieldsets = (
        (None, {
            'fields': ('name', 'year', 'category', 'description')
        }),
        ('Eligibility', {
            'fields': ('min_grade', 'max_grade')
        }),
        ('Voting & Status', {
            'fields': ('status', 'voting_start_date', 'voting_end_date')
        }),
    )
    inlines = [NominationInline, PrizeWinnerInline] # Show nominations and winners directly on the Prize page

@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    list_display = ('player', 'prize', 'nominated_by', 'nomination_date', 'total_vote_score')
    list_filter = ('prize__year', 'prize', 'prize__category')
    search_fields = ('player__first_name', 'player__last_name', 'prize__name')
    readonly_fields = ('nomination_date', 'total_vote_score')
    raw_id_fields = ('prize', 'player', 'nominated_by')
    # We might add votes as an inline here later if needed

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('nomination', 'voter', 'rank', 'voted_at')
    list_filter = ('nomination__prize__year', 'nomination__prize', 'voter', 'rank')
    search_fields = ('nomination__player__first_name', 'nomination__player__last_name', 'nomination__prize__name', 'voter__username')
    readonly_fields = ('voted_at',)
    raw_id_fields = ('nomination', 'voter')

@admin.register(PrizeWinner)
class PrizeWinnerAdmin(admin.ModelAdmin):
    list_display = ('player', 'prize', 'year', 'award_date')
    list_filter = ('year', 'prize__category', 'prize')
    search_fields = ('player__first_name', 'player__last_name', 'prize__name', 'year')
    raw_id_fields = ('prize', 'player', 'awarded_by')
    date_hierarchy = 'award_date'