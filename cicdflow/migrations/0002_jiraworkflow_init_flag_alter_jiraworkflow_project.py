# Generated by Django 4.1.3 on 2023-02-28 07:53

import cicdflow.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cicdflow', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='jiraworkflow',
            name='init_flag',
            field=models.JSONField(default=cicdflow.models.init_data, verbose_name='初始化升级标志'),
        ),
        migrations.AlterField(
            model_name='jiraworkflow',
            name='project',
            field=models.CharField(blank=True, max_length=16, verbose_name='归属项目'),
        ),
    ]
