# create_project.sh
#!/bin/bash

echo "Создание проекта для Railway..."
mkdir -p dota2-bot-railway
cd dota2-bot-railway

# Создаем все файлы как указано выше
# Копируйте содержание каждого файла в соответствующий файл

echo "Проект создан! Теперь:"
echo "1. Добавьте BOT_TOKEN и STEAM_API_KEY в Railway Variables"
echo "2. Подключите GitHub репозиторий к Railway"
echo "3. Нажмите Deploy"