from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0003_matchresult_opponent_alter_matchresult_opponent_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='school',
            field=models.CharField(blank=True, help_text='The school the player attends.', max_length=100),
        ),
    ]