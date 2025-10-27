# awards/admin.py
from django.contrib import admin
from .models import Prize, PrizeCategory, Vote, PrizeWinner

@admin.register(PrizeCategory)
class PrizeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'year',
        'category',
        'status',
        'gender_eligibility', # Correctly added here
        'min_grade',
        'max_grade',
        'voting_opens',
        'voting_closes',
        'winner_player_name',
        'created_at'
    )
    # Also add gender_eligibility to list_filter
    list_filter = ('year', 'status', 'category', 'gender_eligibility', 'min_grade', 'max_grade', 'voting_opens', 'voting_closes')
    search_fields = ('name', 'description', 'winner__player__first_name', 'winner__player__last_name')
    ordering = ('-year', 'category__name', 'name')
    readonly_fields = ('created_at', 'updated_at', 'winner')
    fieldsets = (
        (None, {
            'fields': ('name', 'year', 'category', 'description')
        }),
        ('Status & Voting', {
            'fields': ('status', ('voting_opens', 'voting_closes'))
        }),
        ('Eligibility', {
            # --- ADD 'gender_eligibility' HERE ---
            'fields': ('gender_eligibility', ('min_grade', 'max_grade'),)
        }),
        ('Winner Info (Readonly)', {
            'fields': ('winner',),
             'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Winner', ordering='winner__player__last_name')
    def winner_player_name(self, obj):
        if obj.winner and obj.winner.player:
            return obj.winner.player.full_name
        return "–"


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('prize', 'player', 'voter', 'voted_at')
    list_filter = ('prize__year', 'prize__category', 'prize', 'voter')
    search_fields = ('prize__name', 'player__first_name', 'player__last_name', 'voter__username')
    ordering = ('-voted_at',)
    readonly_fields = ('prize', 'player', 'voter', 'voted_at')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(PrizeWinner)
class PrizeWinnerAdmin(admin.ModelAdmin):
    list_display = ('prize_name', 'player', 'year', 'final_score', 'awarded_by', 'award_date')
    list_filter = ('year', 'prize__category')
    search_fields = ('prize__name', 'player__first_name', 'player__last_name', 'awarded_by__username')
    ordering = ('-year', 'prize__category__name', 'prize__name')
    readonly_fields = ('prize', 'player', 'year', 'final_score', 'awarded_by', 'award_date')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Prize', ordering='prize__name')
    def prize_name(self, obj):
        return str(obj.prize)