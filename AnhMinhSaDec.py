import pygame
import random
import os
import sys
import math
from collections import defaultdict

# -------- CONFIG ----------
WIDTH, HEIGHT = 640, 800
FPS = 60

PLAYER_SPEED = 5
BULLET_SPEED = -10
SCROLL_SPEED = 2
ENEMY_SPAWN_INTERVAL = 150  # using world_y units like original

MAX_LEVEL = 5
MAX_LIVES = 5

# Item/power config
ITEM_DROP_CHANCE = 0.30  # 30% chance to drop an item on enemy death
POWER_DURATION_MIN = 8000  # ms
POWER_DURATION_MAX = 10000  # ms

# -------- INIT ----------
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
try:
    pygame.mixer.init()
except Exception:
    pass

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders - Fixed & Upgraded")
clock = pygame.time.Clock()

# -------- LOAD ASSETS ----------
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")

def safe_load_image(path, convert_alpha=True):
    try:
        img = pygame.image.load(path)
        return img.convert_alpha() if convert_alpha else img.convert()
    except Exception:
        return None

# background - try to load, fallback to fill
bg_img = safe_load_image(os.path.join(ASSET_DIR, "background.png"), convert_alpha=False)
if bg_img:
    background = pygame.transform.scale(bg_img, (WIDTH, HEIGHT))
else:
    # create simple background
    background = pygame.Surface((WIDTH, HEIGHT))
    background.fill((12, 12, 30))

# player image - keep size exactly as original code did (100x100)
player_img_raw = safe_load_image(os.path.join(ASSET_DIR, "player.png"))
if player_img_raw:
    try:
        player_img = pygame.transform.smoothscale(player_img_raw, (100, 100))
    except Exception:
        player_img = player_img_raw
else:
    # fallback: simple triangle ship
    player_img = pygame.Surface((100,100), pygame.SRCALPHA)
    pygame.draw.polygon(player_img, (200,200,255), [(50,0),(90,90),(10,90)])

enemy_img_raw = safe_load_image(os.path.join(ASSET_DIR, "enemy.png"))
if enemy_img_raw:
    try:
        enemy_img = pygame.transform.scale(enemy_img_raw, (50, 50))
    except Exception:
        enemy_img = enemy_img_raw
else:
    enemy_img = pygame.Surface((50,50), pygame.SRCALPHA)
    pygame.draw.circle(enemy_img, (220,180,80), (25,25), 22)

explosion_img_raw = safe_load_image(os.path.join(ASSET_DIR, "explosion.png"))
if explosion_img_raw:
    try:
        explosion_img = pygame.transform.scale(explosion_img_raw, (50,50))
    except Exception:
        explosion_img = explosion_img_raw
else:
    explosion_img = pygame.Surface((50,50), pygame.SRCALPHA)
    pygame.draw.circle(explosion_img, (255,120,10), (25,25), 24)

# Sounds: use safe loader, fallback to dummy
def safe_load_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except Exception:
        class Dummy:
            def play(self): pass
        return Dummy()

shoot_sound = safe_load_sound(os.path.join(ASSET_DIR, "shoot.wav"))
explosion_sound = safe_load_sound(os.path.join(ASSET_DIR, "explosion.wav"))
fireworks_sound = safe_load_sound(os.path.join(ASSET_DIR, "fireworks.wav"))
pickup_sound = safe_load_sound(os.path.join(ASSET_DIR, "fireworks.wav"))

# background music: use music channel for mp3 if present
bg_music_path = os.path.join(ASSET_DIR, "background_music.mp3")
if os.path.exists(bg_music_path):
    try:
        pygame.mixer.music.load(bg_music_path)
        pygame.mixer.music.set_volume(0.5)
    except Exception:
        pass
# --- Item / Power-up images ---

energy_img = safe_load_image(os.path.join(ASSET_DIR, "a glowing blue energ.png"))   # Power-up: tăng sát thương đạn
shield_img = safe_load_image(os.path.join(ASSET_DIR, "a glowing blue shiel.png"))   # Power-up: khiên bảo vệ
mystery_img = safe_load_image(os.path.join(ASSET_DIR, "a mysterious purple .png"))  # Power-up: hiệu ứng ngẫu nhiên
speed_img = safe_load_image(os.path.join(ASSET_DIR, "a yellow lightning b.png"))    # Power-up: tăng tốc hoặc tốc độ bắn
heart_img = safe_load_image(os.path.join(ASSET_DIR, "heart.png"))                   # Hồi máu / thêm mạng

# (Tuỳ chọn) nếu bạn có hệ thống rơi vật phẩm:
item_images = {
    "energy": energy_img,
    "shield": shield_img,
    "mystery": mystery_img,
    "speed": speed_img,
    "heart": heart_img,
}

# -------- FUNCTIONS ----------
def reset_game():
    global level, lives, enemies_destroyed, enemies_required
    global game_over, game_win, bg_y, world_y, last_enemy_spawn
    global all_sprites, enemies, bullets, player, items, restart_btn, wave, spawn_interval

    level = 1
    lives = MAX_LIVES
    enemies_destroyed = 0
    enemies_required = 5 + level * 3
    game_over = False
    game_win = False
    bg_y = 0
    world_y = 0
    last_enemy_spawn = 0

    all_sprites.empty()
    enemies.empty()
    bullets.empty()
    items.empty()

    player = Player()
    all_sprites.add(player)

    wave = 1
    spawn_interval = 900  # ms base spawn timer (used in wave logic)

    # restart button rect placeholder
    restart_btn = pygame.Rect(0,0,0,0)

def draw_restart_icon():
    center = (WIDTH // 2, HEIGHT // 2 + 60)
    radius = 25
    pygame.draw.circle(screen, (100, 100, 100), center, radius)

    arrow_w, arrow_h = 10, 12
    arrow_x = center[0] - arrow_w // 2
    arrow_y = center[1] - arrow_h // 2

    pygame.draw.polygon(screen, (255, 255, 255), [
        (arrow_x, arrow_y),
        (arrow_x + arrow_w, center[1]),
        (arrow_x, arrow_y + arrow_h),
    ])

    return pygame.Rect(center[0] - radius, center[1] - radius, radius*2, radius*2)

def click_on_restart(pos):
    center = (WIDTH // 2, HEIGHT // 2 + 60)
    radius = 25
    dx = pos[0] - center[0]
    dy = pos[1] - center[1]
    return dx*dx + dy*dy <= radius*radius

# -------- GAME STATE ----------
level = 1
lives = MAX_LIVES
enemies_destroyed = 0
enemies_required = 5 + level * 3
game_over = False
game_win = False
show_menu = True
level_transition = False
level_transition_start = 0
transition_duration = 2000 
# -------- CLASSES ----------
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = player_img
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 50))
        self.show_flame = False
        self.last_shot_time = 0
        self.shoot_cooldown = 180  # ms default
        self.powers = {}  # name -> expire_time_ms
        self.invulnerable_until = 0

    def update(self):
        keys = pygame.key.get_pressed()
        self.show_flame = False
        if keys[pygame.K_LEFT] and self.rect.left > 0:
            self.rect.x -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] and self.rect.right < WIDTH:
            self.rect.x += PLAYER_SPEED
        if keys[pygame.K_UP] and self.rect.top > HEIGHT//2:
            self.rect.y -= PLAYER_SPEED
        if keys[pygame.K_DOWN] and self.rect.bottom < HEIGHT:
            self.rect.y += PLAYER_SPEED
        if keys[pygame.K_UP]:
            self.show_flame = True

        # Shooting while holding space (continuous shooting)
        now = pygame.time.get_ticks()
        cooldown = self.shoot_cooldown
        if 'fast_fire' in self.powers:
            cooldown = max(20, int(self.shoot_cooldown * 0.6))

        if keys[pygame.K_SPACE]:
            if now - self.last_shot_time >= cooldown:
                self.shoot()
                self.last_shot_time = now

        # expire powers
        expired = [k for k,v in self.powers.items() if pygame.time.get_ticks() >= v]
        for k in expired:
            del self.powers[k]

        # invul flicker
        if pygame.time.get_ticks() < self.invulnerable_until:
            alpha = 120 if (pygame.time.get_ticks() // 100) % 2 == 0 else 255
            try:
                self.image = player_img.copy()
                self.image.set_alpha(alpha)
            except Exception:
                pass
        else:
            self.image = player_img.copy()

    def shoot(self):
        # shoot method: respects multi_shot
        if 'multi_shot' in self.powers:
            offsets = [-28, 0, 28]
            for off in offsets:
                bullet = Bullet(self.rect.centerx + off, self.rect.top)
                all_sprites.add(bullet); bullets.add(bullet)
            shoot_sound.play()
        else:
            bullet = Bullet(self.rect.centerx, self.rect.top)
            all_sprites.add(bullet); bullets.add(bullet)
            shoot_sound.play()

    def draw(self, surface):
        surface.blit(self.image, self.rect)
        if self.show_flame:
            flame = pygame.Surface((20, 30), pygame.SRCALPHA)
            pygame.draw.polygon(flame, (255, 100, 0), [(10, 0), (0, 30), (20, 30)])
            surface.blit(flame, (self.rect.centerx - 10, self.rect.bottom))

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = enemy_img
        self.rect = self.image.get_rect(topleft=(x, y))
        self.hp = 1
        # give variety
        self.type = random.choice(['straight', 'zigzag', 'fast'])
        self.spawn_time = pygame.time.get_ticks()
        if self.type == 'fast':
            self.speed = SCROLL_SPEED + 2
        else:
            self.speed = SCROLL_SPEED

    def update(self):
        global lives, game_over
        # pattern
        if self.type == 'zigzag':
            t = (pygame.time.get_ticks() - self.spawn_time) / 200.0
            self.rect.x += int(math.sin(t) * 2)
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()
            lives -= 1
            if lives <= 0:
                game_over = True

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((12, 28), pygame.SRCALPHA)
        # Vẽ viên đạn hình elip với gradient
        for i in range(28):
            r = max(0, 255 - i * 8)
            g = max(0, 200 - i * 6)
            color = (255, g, 0)
            pygame.draw.ellipse(self.image, color, (1, i, 10, 10))
        # Glow effect
        glow = pygame.Surface((24, 48), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 255, 0, 60), glow.get_rect())
        self.image.blit(glow, (-6, -10))
        self.rect = self.image.get_rect(midbottom=(x, y))

    def update(self):
        self.rect.y += BULLET_SPEED
        if self.rect.bottom < 0:
            self.kill()

class Explosion(pygame.sprite.Sprite):
    def __init__(self, center):
        super().__init__()
        self.image = explosion_img
        self.rect = self.image.get_rect(center=center)
        self.timer = 12

    def update(self):
        self.timer -= 1
        if self.timer <= 0:
            self.kill()

class Item(pygame.sprite.Sprite):
    # types: health, fast_fire, multi_shot
    def __init__(self, x, y, typ):
        super().__init__()
        self.type = typ
        # Prefer specific asset images for items (from item_images dict).
        # Fall back to tinted bullet-shaped sprite when asset missing.
        img = None
        # map our internal types to keys in item_images
        key_map = {
            'health': 'heart',
            'fast_fire': 'speed',
            'multi_shot': 'energy',
        }
        use_key = key_map.get(typ, 'mystery')
        asset_img = item_images.get(use_key)
        if asset_img:
            try:
                img = pygame.transform.smoothscale(asset_img, (32, 32))
            except Exception:
                img = asset_img.copy()

        if img is None:
            # fallback: use bullet image tinted by type
            img_b = safe_load_image(os.path.join(ASSET_DIR, "bullet.png"))
            if img_b:
                try:
                    img = pygame.transform.smoothscale(img_b, (28, 28))
                except Exception:
                    img = img_b.copy()
            else:
                img = pygame.Surface((28,28), pygame.SRCALPHA)
                pygame.draw.circle(img, (200,200,200), (14,14), 12)

            img = img.copy()
            if typ == 'health':
                tint = (220,40,60)
            elif typ == 'fast_fire':
                tint = (60,200,220)
            else:
                tint = (220,200,60)
            tint_surf = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            tint_surf.fill(tint + (0,))
            img.blit(tint_surf, (0,0), special_flags=pygame.BLEND_RGB_ADD)

        self.image = img
        self.rect = self.image.get_rect(center=(x,y))
        self.vy = 2.4
        self.spawn_time = pygame.time.get_ticks()

    def update(self):
        self.rect.y += self.vy
        if pygame.time.get_ticks() - self.spawn_time > 10000:
            self.kill()
        if self.rect.top > HEIGHT + 20:
            self.kill()

# -------- GROUPS ----------
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
bullets = pygame.sprite.Group()
items = pygame.sprite.Group()

player = Player()
all_sprites.add(player)

# -------- BACKGROUND SCROLL ----------
bg_y = 0
world_y = 0
last_enemy_spawn = 0

# -------- OTHER STATE ----------
restart_btn = pygame.Rect(0,0,0,0)
wave = 1
spawn_interval = 900  # ms base spawn interval used for wave difficulty

# -------- GAME LOOP ----------
running = True

# Start screen music only when starting
while running:
    clock.tick(FPS)

    if show_menu:
        screen.blit(background, (0, 0))
        font = pygame.font.SysFont(None, 72)
        title = font.render("SPACE INVADERS", True, (255, 255, 255))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 100))

        start_btn = pygame.Rect(WIDTH//2 - 75, HEIGHT//2, 150, 50)
        pygame.draw.rect(screen, (100, 100, 100), start_btn)
        font = pygame.font.SysFont(None, 36)
        txt = font.render("Start", True, (255, 255, 255))
        screen.blit(txt, (start_btn.centerx - txt.get_width()//2, start_btn.centery - txt.get_height()//2))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if start_btn.collidepoint(event.pos):
                    show_menu = False
                    # play background music if available
                    try:
                        pygame.mixer.music.play(loops=-1)
                    except Exception:
                        pass
        continue

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif game_over and event.type == pygame.MOUSEBUTTONDOWN:
            if click_on_restart(event.pos):
                reset_game()
        elif not game_over and not game_win and event.type == pygame.KEYDOWN:
            # For compatibility: still allow single-shot on press
            if event.key == pygame.K_SPACE:
                player.shoot()

    if game_over or game_win:
        screen.blit(background, (0, bg_y % HEIGHT))
        screen.blit(background, (0, (bg_y % HEIGHT) - HEIGHT))
        font = pygame.font.SysFont(None, 72)
        if game_win:
            msg = font.render("YOU WIN!", True, (255, 255, 0))
            try:
                fireworks_sound.play()
            except Exception:
                pass
        else:
            msg = font.render("GAME OVER", True, (255, 0, 0))
        screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2))

        if game_over:
            restart_btn = draw_restart_icon()

        pygame.display.flip()
        continue

    # --- UPDATE & SPAWN ---
    all_sprites.update()
    items.update()
    bullets.update()
    enemies.update()

    bg_y += SCROLL_SPEED
    world_y += SCROLL_SPEED

    if world_y - last_enemy_spawn > ENEMY_SPAWN_INTERVAL:
        last_enemy_spawn = world_y
        enemy_count = 1 if level < 3 else 2
        for _ in range(enemy_count):
            x = random.randint(20, WIDTH - 70)
            y = random.randint(-300, -30)
            enemy = Enemy(x, y)
            all_sprites.add(enemy)
            enemies.add(enemy)

    # --- COLLISIONS & LEVEL UP ---
    hits = pygame.sprite.groupcollide(enemies, bullets, True, True)
    for hit in hits:
        try:
            explosion_sound.play()
        except Exception:
            pass
        explosion = Explosion(hit.rect.center)
        all_sprites.add(explosion)
        enemies_destroyed += 1

        # item drop chance
        if random.random() < ITEM_DROP_CHANCE:
            typ = random.choice(["health", "fast_fire", "multi_shot"])
            it = Item(hit.rect.centerx, hit.rect.centery, typ)
            items.add(it); all_sprites.add(it)

        if enemies_destroyed >= enemies_required:
            if level < MAX_LEVEL:
                level += 1
                enemies_destroyed = 0
                enemies_required = 5 + level * 3
                level_transition = True
                level_transition_start = pygame.time.get_ticks()
            else:
                game_win = True


    # --- PLAYER HIT ---
    if pygame.time.get_ticks() > player.invulnerable_until:
        hits_p = pygame.sprite.spritecollide(player, enemies, True, pygame.sprite.collide_rect)
        if hits_p:
            lives -= len(hits_p)
            player.invulnerable_until = pygame.time.get_ticks() + 1200
            if lives <= 0:
                lives = 0; game_over = True

    # --- PLAYER PICKUPS ---
    pickups = pygame.sprite.spritecollide(player, items, True, pygame.sprite.collide_rect)
    for it in pickups:
        try:
            pickup_sound.play()
        except Exception:
            pass
        if it.type == "health":
            if lives < MAX_LIVES:
                lives += 1
        elif it.type == "fast_fire":
            dur = random.randint(POWER_DURATION_MIN, POWER_DURATION_MAX)
            player.powers['fast_fire'] = pygame.time.get_ticks() + dur
        elif it.type == "multi_shot":
            dur = random.randint(POWER_DURATION_MIN, POWER_DURATION_MAX)
            player.powers['multi_shot'] = pygame.time.get_ticks() + dur
       

    # --- DRAWING ---
    screen.blit(background, (0, bg_y % HEIGHT))
    screen.blit(background, (0, (bg_y % HEIGHT) - HEIGHT))

    for sprite in all_sprites:
        if sprite != player:
            screen.blit(sprite.image, sprite.rect)
    player.draw(screen)

    # draw items and bullets on top
    for it in items:
        screen.blit(it.image, it.rect)
    for b in bullets:
        screen.blit(b.image, b.rect)

    font = pygame.font.SysFont(None, 28)
    hud = font.render(f"Level: {level}   Lives: {lives}", True, (255, 255, 255))
    screen.blit(hud, (10, 10))
    enemy_info = font.render(f"Enemies: {enemies_destroyed}/{enemies_required}", True, (255, 255, 255))
    screen.blit(enemy_info, (10, 40))

    # show active powers timers
    now = pygame.time.get_ticks()
    x = WIDTH - 8; y = 8
    for name, expire in list(player.powers.items()):
        rem = max(0, (expire - now) // 1000)
        if name == 'fast_fire':
            txt = f"FastFire: {rem}s"
        elif name == 'multi_shot':
            txt = f"MultiShot: {rem}s"
        else:
            txt = f"{name}: {rem}s"
        surf = font.render(txt, True, (230,230,230))
        r = surf.get_rect(topright=(x,y))
        screen.blit(surf, r)
        y += surf.get_height() + 6


    # --- LEVEL TRANSITION EFFECT (fade in/out, non-blocking) ---
        if level_transition:
            elapsed = pygame.time.get_ticks() - level_transition_start
            if elapsed < transition_duration:
                # Tính alpha (độ trong suốt) từ 0→255→0
                half = transition_duration / 2
                if elapsed < half:
                    alpha = int((elapsed / half) * 255)
                else:
                    alpha = int(((transition_duration - elapsed) / half) * 255)

                # Tạo surface mờ dần
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                text = pygame.font.SysFont(None, 72).render(f"LEVEL {level} START!", True, (255, 255, 0))
                text.set_alpha(alpha)
                overlay.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - text.get_height()//2))
                screen.blit(overlay, (0, 0))
            else:
                level_transition = False
                try:
                        fireworks_sound.play()
                except Exception:
                        pass
                # Kết thúc hiệu ứng chuyển cấp
    pygame.display.flip()

pygame.quit()
sys.exit()