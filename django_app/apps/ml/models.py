from django.db import models


class MLModel(models.Model):
    """Versioned XGBoost model registry."""

    class Status(models.TextChoices):
        TRAINING   = "training",   "Training"
        STAGING    = "staging",    "Staging"
        PRODUCTION = "production", "Production"
        ARCHIVED   = "archived",   "Archived"

    version       = models.CharField(max_length=20, unique=True)
    status        = models.CharField(max_length=12, choices=Status.choices, default=Status.STAGING, db_index=True)
    artifact_path = models.CharField(max_length=255)

    # Quality metrics
    auc_roc      = models.FloatField()
    precision    = models.FloatField()
    recall       = models.FloatField()
    f1_score     = models.FloatField()
    sharpe_ratio = models.FloatField(null=True, blank=True)

    # Training metadata
    train_from    = models.DateTimeField()
    train_to      = models.DateTimeField()
    train_samples = models.IntegerField()
    features_list = models.JSONField(default=list)
    hyperparams   = models.JSONField(default=dict)

    created_at  = models.DateTimeField(auto_now_add=True)
    deployed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ml_models"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MLModel v{self.version} [{self.status}] AUC:{self.auc_roc:.3f}"
