from django.contrib import admin
from .models import MLModel


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display  = ("version", "status", "auc_roc", "f1_score", "train_samples", "created_at", "deployed_at")
    list_filter   = ("status",)
    ordering      = ("-created_at",)
    readonly_fields = ("created_at",)

    actions = ["promote_to_production"]

    @admin.action(description="Promote selected model to Production")
    def promote_to_production(self, request, queryset):
        MLModel.objects.filter(status="production").update(status="archived")
        queryset.update(status="production")
        self.message_user(request, "Model promoted to production.")
