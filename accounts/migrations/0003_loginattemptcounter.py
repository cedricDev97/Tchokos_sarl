from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_userprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttemptCounter",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
        ),
    ]
