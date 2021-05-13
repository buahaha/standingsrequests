# Generated by Django 3.1.10 on 2021-05-13 14:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("standingsrequests", "0008_add_revocation_reason"),
    ]

    operations = [
        migrations.AlterField(
            model_name="standingrevocation",
            name="reason",
            field=models.CharField(
                choices=[
                    ("NO", "None recorded"),
                    ("OR", "Requested by character owner"),
                    ("LP", "Character owner has lost permission"),
                    ("CT", "Not all corp tokens are recorded in Auth."),
                    ("RG", "Standing has been revoked in game"),
                ],
                default="NO",
                max_length=2,
            ),
        ),
    ]
