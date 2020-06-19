# Generated by Django 2.2.13 on 2020-06-18 18:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("standingsrequests", "0003_rename_non_pep"),
    ]

    operations = [
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="action_by",
            field=models.ForeignKey(
                default=None,
                help_text="standing manager that accepted or rejected this requests",
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="action_date",
            field=models.DateTimeField(
                help_text="datetime of action by standing manager", null=True
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="contact_id",
            field=models.PositiveIntegerField(
                db_index=True, help_text="EVE Online ID of contact this standing is for"
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="contact_type_id",
            field=models.PositiveIntegerField(
                db_index=True, help_text="EVE Online Type ID of this contact"
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="effective_date",
            field=models.DateTimeField(
                help_text="Datetime when this standing was set active in-game",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="is_effective",
            field=models.BooleanField(
                default=False,
                help_text="True, when this standing is also set in-game, else False",
            ),
        ),
        migrations.AlterField(
            model_name="abstractstandingsrequest",
            name="request_date",
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                help_text="datetime this request was created",
            ),
        ),
        migrations.AlterField(
            model_name="alliancestanding",
            name="contact_id",
            field=models.PositiveIntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name="alliancestanding",
            name="standing",
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name="characterassociation",
            name="alliance_id",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="characterassociation",
            name="character_id",
            field=models.PositiveIntegerField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="characterassociation",
            name="corporation_id",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="characterassociation",
            name="main_character_id",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="contactlabel",
            name="label_id",
            field=models.BigIntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name="contactset",
            name="date",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="corpstanding",
            name="contact_id",
            field=models.PositiveIntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name="corpstanding",
            name="standing",
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name="evenamecache",
            name="entity_id",
            field=models.PositiveIntegerField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="pilotstanding",
            name="contact_id",
            field=models.PositiveIntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name="pilotstanding",
            name="standing",
            field=models.FloatField(db_index=True),
        ),
    ]
