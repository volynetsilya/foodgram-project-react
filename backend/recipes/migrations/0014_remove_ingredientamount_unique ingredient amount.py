# Generated by Django 4.1.6 on 2023-03-03 17:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0013_alter_subscription_options'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='ingredientamount',
            name='unique ingredient amount',
        ),
    ]