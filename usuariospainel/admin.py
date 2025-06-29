from django.contrib import admin
from .models import UserCompanyLink

@admin.register(UserCompanyLink)
class UserCompanyLinkAdmin(admin.ModelAdmin):
    list_display = ('user', 'empresa', 'position', 'status', 'created_at', 'expires_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'empresa__nome_fantasia', 'position')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
