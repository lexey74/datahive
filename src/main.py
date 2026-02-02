"""
SecBrain - Instagram Content to Knowledge Base CLI
"""
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from config import Config
from modules.pipeline import SecBrainPipeline


console = Console()


def display_banner() -> None:
    """Отображение welcome banner"""
    banner = """
    ╔═══════════════════════════════════════════╗
    ║     🧠 SecBrain - Instagram to Notes     ║
    ║   Privacy-First Knowledge Base Builder   ║
    ╚═══════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold cyan"))


def check_prerequisites() -> bool:
    """Проверка необходимых зависимостей"""
    issues = []
    
    # Проверка Ollama
    try:
        import ollama
        console.print("✅ Ollama library installed", style="green")
    except ImportError:
        issues.append("❌ Ollama не установлен: pip install ollama")
    
    # Проверка faster-whisper
    try:
        import faster_whisper
        console.print("✅ faster-whisper installed", style="green")
    except ImportError:
        issues.append("❌ faster-whisper не установлен: pip install faster-whisper")
    
    # Проверка yt-dlp
    import subprocess
    try:
        result = subprocess.run(
            ['yt-dlp', '--version'], 
            capture_output=True, 
            check=True,
            timeout=5
        )
        console.print("✅ yt-dlp found", style="green")
    except subprocess.TimeoutExpired:
        issues.append("❌ yt-dlp не отвечает (timeout)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append("❌ yt-dlp не установлен: pip install yt-dlp")
    
    # Проверка FFmpeg
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], 
            capture_output=True, 
            check=True,
            timeout=5
        )
        console.print("✅ FFmpeg found", style="green")
    except subprocess.TimeoutExpired:
        issues.append("❌ FFmpeg не отвечает (timeout)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append("❌ FFmpeg не установлен")
    
    if issues:
        console.print("\n[bold red]Проблемы с зависимостями:[/bold red]")
        for issue in issues:
            console.print(issue)
        return False
    
    return True


def main() -> None:
    """Главная функция CLI"""
    display_banner()
    
    # Загрузка конфигурации
    config = Config()
    console.print(f"📁 Output: {config.get('output_dir')}", style="dim")
    console.print(f"🤖 Model: {config.get('ollama_model')}", style="dim")
    console.print()
    
    # Проверка зависимостей
    if not check_prerequisites():
        console.print("\n⚠️  Установите недостающие компоненты перед запуском", style="yellow")
        return
    
    console.print()
    
    # Инициализация пайплайна
    try:
        pipeline = SecBrainPipeline(config.as_dict())
    except Exception as e:
        console.print(f"❌ Ошибка инициализации: {e}", style="red")
        return
    
    # Основной цикл
    while True:
        console.print("\n" + "─" * 60)
        url = Prompt.ask(
            "[bold cyan]Instagram URL[/bold cyan] (или 'quit' для выхода)",
            default=""
        )
        
        if url.lower() in ['quit', 'exit', 'q']:
            console.print("👋 До встречи!", style="bold green")
            break
        
        if not url or 'instagram.com' not in url:
            console.print("⚠️  Введите корректный Instagram URL", style="yellow")
            continue
        
        # Обработка URL
        try:
            note_path = pipeline.process(url)
            if note_path:
                console.print(f"\n✨ Заметка создана: [link]{note_path}[/link]", style="bold green")
        except KeyboardInterrupt:
            console.print("\n⏸️  Прервано пользователем", style="yellow")
        except Exception as e:
            console.print(f"\n❌ Ошибка: {e}", style="red")


if __name__ == "__main__":
    main()
