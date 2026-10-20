-- Frozen from an empty PostgreSQL 18 database upgraded through b7e3d9c1a5f2.
-- Contains schema and migration-owned objective/prompt seeds, never local player data.
CREATE TYPE public.agegroupenum AS ENUM (
    'CHILD',
    'TEEN',
    'ADULT',
    'ELDER'
);
CREATE TYPE public.arenamode AS ENUM (
    'DUEL',
    'BRAWL',
    'HUNT'
);
CREATE TYPE public.availabilityenum AS ENUM (
    'VAULT',
    'DEPARTURE',
    'POOL',
    'MARKET',
    'ARCHIVE'
);
CREATE TYPE public.craftingorderstatus AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'COLLECTED',
    'CANCELLED'
);
CREATE TYPE public.deathcauseenum AS ENUM (
    'HEALTH',
    'RADIATION',
    'INCIDENT',
    'EXPLORATION',
    'COMBAT',
    'EXILE'
);
CREATE TYPE public.dwellerlocationrelationenum AS ENUM (
    'ORIGIN',
    'VISITED'
);
CREATE TYPE public.dwellerstatusenum AS ENUM (
    'IDLE',
    'WORKING',
    'EXPLORING',
    'TRAINING',
    'RESTING',
    'DEAD',
    'QUESTING',
    'FIGHTING'
);
CREATE TYPE public.expeditionrunstatus AS ENUM (
    'IN_ROOM',
    'RETREATED',
    'CLEARED',
    'DIED'
);
CREATE TYPE public.explorationstatus AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'RECALLED',
    'RETURNING'
);
CREATE TYPE public.genderenum AS ENUM (
    'MALE',
    'FEMALE'
);
CREATE TYPE public.hazardteam AS ENUM (
    'FIRE',
    'RADIATION'
);
CREATE TYPE public.incidentstatus AS ENUM (
    'ACTIVE',
    'SPREADING',
    'RESOLVED',
    'FAILED'
);
CREATE TYPE public.incidenttype AS ENUM (
    'RAIDER_ATTACK',
    'RADROACH_INFESTATION',
    'MOLE_RAT_ATTACK',
    'DEATHCLAW_ATTACK',
    'FERAL_GHOUL_ATTACK',
    'FIRE',
    'RADSCORPION_ATTACK'
);
CREATE TYPE public.junktypeenum AS ENUM (
    'CIRCUITRY',
    'LEATHER',
    'ADHESIVE',
    'CLOTH',
    'SCIENCE',
    'STEEL',
    'VALUABLES'
);
CREATE TYPE public.lifecycleenum AS ENUM (
    'ALIVE',
    'DEAD_REVIVABLE',
    'DEAD_PERMANENT',
    'WASTELAND'
);
CREATE TYPE public.locationtypeenum AS ENUM (
    'ORIGIN',
    'VISITED',
    'DISCOVERY',
    'HOME_VAULT'
);
CREATE TYPE public.notificationpriority AS ENUM (
    'INFO',
    'NORMAL',
    'HIGH',
    'URGENT'
);
CREATE TYPE public.notificationtype AS ENUM (
    'EXPLORATION_UPDATE',
    'EXPLORATION_COMPLETE',
    'LEVEL_UP',
    'TRAINING_COMPLETE',
    'TRAINING_STARTED',
    'RELATIONSHIP_FORMED',
    'PREGNANCY_DETECTED',
    'BABY_BORN',
    'COMBAT_STARTED',
    'COMBAT_VICTORY',
    'COMBAT_DEFEAT',
    'DWELLER_INJURED',
    'RESOURCE_LOW',
    'RESOURCE_CRITICAL',
    'POWER_OUTAGE',
    'QUEST_COMPLETE',
    'ACHIEVEMENT_UNLOCKED',
    'RADIO_NEW_DWELLER',
    'DWELLER_DIED',
    'MAP_REGISTRATION_FAILED',
    'CRAFTING_COMPLETE',
    'DWELLER_EXIT_REQUESTED',
    'HAZARD_TEAM_JOINED',
    'RADIO_AUTO_SWITCHED_TO_HAPPINESS',
    'LOCATION_CLEARED',
    'LOCATION_READY',
    'RECIPE_UNLOCKED',
    'OBJECTIVE_COMPLETED',
    'ARENA_MORALE_BOOST',
    'OBJECTIVES_REFRESHED'
);
CREATE TYPE public.outfittypeenum AS ENUM (
    'COMMON',
    'RARE',
    'LEGENDARY',
    'POWER_ARMOR',
    'TIERED'
);
CREATE TYPE public.placekind AS ENUM (
    'PLACE',
    'VAULT'
);
CREATE TYPE public.pregnancystatusenum AS ENUM (
    'PREGNANT',
    'DELIVERED',
    'MISCARRIED'
);
CREATE TYPE public.questtype AS ENUM (
    'MAIN',
    'SIDE',
    'DAILY',
    'EVENT',
    'REPEATABLE'
);
CREATE TYPE public.rarityenum AS ENUM (
    'COMMON',
    'RARE',
    'LEGENDARY'
);
CREATE TYPE public.relationshiptypeenum AS ENUM (
    'ACQUAINTANCE',
    'FRIEND',
    'ROMANTIC',
    'PARTNER',
    'EX',
    'MARRIED'
);
CREATE TYPE public.requirementtype AS ENUM (
    'LEVEL',
    'ITEM',
    'ROOM',
    'DWELLER_COUNT',
    'QUEST_COMPLETED',
    'ATTACK',
    'STAT'
);
CREATE TYPE public.rewardtype AS ENUM (
    'CAPS',
    'ITEM',
    'DWELLER',
    'RESOURCE',
    'EXPERIENCE',
    'STIMPAK',
    'RADAWAY',
    'LUNCHBOX'
);
CREATE TYPE public.roomtypeenum AS ENUM (
    'CAPACITY',
    'CRAFTING',
    'MISC',
    'PRODUCTION',
    'QUESTS',
    'THEME',
    'TRAINING',
    'ARENA',
    'RESPONSE'
);
CREATE TYPE public.specialenum AS ENUM (
    'STRENGTH',
    'PERCEPTION',
    'ENDURANCE',
    'CHARISMA',
    'INTELLIGENCE',
    'AGILITY',
    'LUCK'
);
CREATE TYPE public.trainingstatus AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'CANCELLED'
);
CREATE TYPE public.weaponsubtypeenum AS ENUM (
    'BLUNT',
    'EDGED',
    'POINTED',
    'PISTOL',
    'RIFLE',
    'SHOTGUN',
    'AUTOMATIC',
    'EXPLOSIVE',
    'FLAMER'
);
CREATE TYPE public.weapontypeenum AS ENUM (
    'MELEE',
    'GUN',
    'ENERGY',
    'HEAVY'
);
CREATE TABLE public.ai_settings (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    provider character varying(50),
    model character varying(200),
    base_url character varying(500),
    gateway_route character varying(200),
    id uuid NOT NULL
);
CREATE TABLE public.arena_match_event (
    id uuid NOT NULL,
    room_id uuid NOT NULL,
    round_seq integer DEFAULT 1 NOT NULL,
    kind character varying NOT NULL,
    message character varying(200) NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);
CREATE TABLE public.arena_state (
    room_id uuid NOT NULL,
    mode public.arenamode,
    fighter_a_id uuid,
    fighter_b_id uuid,
    fighter_c_id uuid,
    fighter_d_id uuid,
    opponents jsonb,
    last_fight_at timestamp without time zone,
    fight_started_at timestamp without time zone,
    knocked_out_ids jsonb,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    support_bots jsonb,
    skill_charge jsonb,
    queued_skill_ids jsonb,
    next_attack_team character varying(1) DEFAULT 'A'::character varying NOT NULL
);
CREATE TABLE public.chatmessage (
    vault_id uuid NOT NULL,
    from_user_id uuid,
    from_dweller_id uuid,
    to_user_id uuid,
    to_dweller_id uuid,
    message_text character varying(2000) NOT NULL,
    llm_interaction_id uuid,
    audio_url character varying(500),
    transcription character varying(2000),
    audio_duration double precision,
    id uuid NOT NULL,
    created_at timestamp without time zone NOT NULL,
    happiness_delta double precision,
    happiness_reason character varying(255)
);
CREATE TABLE public.craftingorder (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    vault_id uuid NOT NULL,
    room_id uuid NOT NULL,
    item_name character varying(64) NOT NULL,
    item_type character varying(16) NOT NULL,
    rarity public.rarityenum NOT NULL,
    status public.craftingorderstatus NOT NULL,
    progress double precision NOT NULL,
    started_at timestamp without time zone NOT NULL,
    estimated_completion_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone,
    junk_spent integer NOT NULL,
    caps_spent integer NOT NULL,
    required_stat character varying(16) NOT NULL,
    ability_sum_at_start integer NOT NULL,
    item_snapshot jsonb NOT NULL,
    id uuid NOT NULL,
    cancelled_at timestamp without time zone,
    junk_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL
);
CREATE TABLE public.dweller (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    strength integer NOT NULL,
    perception integer NOT NULL,
    endurance integer NOT NULL,
    charisma integer NOT NULL,
    intelligence integer NOT NULL,
    agility integer NOT NULL,
    luck integer NOT NULL,
    first_name character varying(32) NOT NULL,
    last_name character varying(32),
    age_group public.agegroupenum NOT NULL,
    birth_date timestamp without time zone,
    gender public.genderenum NOT NULL,
    rarity public.rarityenum NOT NULL,
    bio character varying(2048),
    visual_attributes jsonb,
    image_url character varying(255),
    thumbnail_url character varying(255),
    level integer NOT NULL,
    experience integer NOT NULL,
    max_health integer NOT NULL,
    health integer NOT NULL,
    radiation integer NOT NULL,
    happiness integer NOT NULL,
    stimpack integer NOT NULL,
    radaway integer NOT NULL,
    status public.dwellerstatusenum NOT NULL,
    id uuid NOT NULL,
    vault_id uuid,
    room_id uuid,
    partner_id uuid,
    parent_1_id uuid,
    parent_2_id uuid,
    is_dead boolean DEFAULT false NOT NULL,
    death_timestamp timestamp without time zone,
    death_cause public.deathcauseenum,
    is_permanently_dead boolean DEFAULT false NOT NULL,
    epitaph character varying(255),
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    apprentice_stat public.specialenum,
    apprentice_started_at timestamp without time zone,
    apprentice_stat_gains json DEFAULT '{}'::json NOT NULL,
    is_traded boolean DEFAULT false NOT NULL,
    bio_entries jsonb DEFAULT '[]'::jsonb NOT NULL,
    exit_requested_at timestamp without time zone,
    despair_since timestamp without time zone,
    lifecycle public.lifecycleenum,
    availability public.availabilityenum,
    previous_vault_id uuid,
    content_provenance character varying(16),
    sharing_consent boolean,
    departed_at timestamp without time zone,
    departure_eligible_at timestamp without time zone
);
CREATE TABLE public.dwellerlocation (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    relation public.dwellerlocationrelationenum NOT NULL,
    id uuid NOT NULL,
    dweller_id uuid NOT NULL,
    location_id uuid NOT NULL,
    is_unlocked boolean DEFAULT false NOT NULL
);
CREATE TABLE public.expeditionrun (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    id uuid NOT NULL,
    exploration_id uuid NOT NULL,
    vault_id uuid NOT NULL,
    site_id character varying(64) NOT NULL,
    room_cursor integer NOT NULL,
    status public.expeditionrunstatus NOT NULL,
    flags jsonb,
    finished_at timestamp without time zone
);
CREATE TABLE public.exploration (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    duration integer NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    status public.explorationstatus NOT NULL,
    events jsonb,
    loot_collected jsonb,
    dweller_strength integer NOT NULL,
    dweller_perception integer NOT NULL,
    dweller_endurance integer NOT NULL,
    dweller_charisma integer NOT NULL,
    dweller_intelligence integer NOT NULL,
    dweller_agility integer NOT NULL,
    dweller_luck integer NOT NULL,
    total_distance integer NOT NULL,
    total_caps_found integer NOT NULL,
    enemies_encountered integer NOT NULL,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    dweller_id uuid NOT NULL,
    stimpaks integer DEFAULT 0 NOT NULL,
    radaways integer DEFAULT 0 NOT NULL,
    unclaimed_loot jsonb DEFAULT '[]'::jsonb NOT NULL,
    return_started_at timestamp without time zone,
    return_completes_at timestamp without time zone,
    recalled_early boolean DEFAULT false NOT NULL,
    target_location_id uuid,
    clear_tier integer,
    team_id uuid,
    world_version integer,
    origin_x double precision,
    origin_y double precision,
    heading_degrees double precision,
    pos_x double precision,
    pos_y double precision,
    trail jsonb,
    position_as_of timestamp without time zone,
    paused_at timestamp without time zone
);
CREATE TABLE public.gamestate (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    last_tick_time timestamp without time zone NOT NULL,
    is_active boolean NOT NULL,
    is_paused boolean NOT NULL,
    total_game_time integer NOT NULL,
    paused_at timestamp without time zone,
    resumed_at timestamp without time zone,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    last_activity_time timestamp without time zone NOT NULL,
    water_empty_since timestamp without time zone,
    resource_remainders json DEFAULT '{}'::json NOT NULL,
    last_presence_at timestamp without time zone,
    daily_objectives_period timestamp without time zone,
    weekly_objectives_period timestamp without time zone,
    achievement_tracks_initialized boolean DEFAULT false NOT NULL
);
CREATE TABLE public.incident (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    type public.incidenttype NOT NULL,
    status public.incidentstatus NOT NULL,
    difficulty integer NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    duration integer NOT NULL,
    damage_dealt integer NOT NULL,
    enemies_defeated integer NOT NULL,
    loot jsonb,
    rooms_affected jsonb,
    spread_count integer NOT NULL,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    room_id uuid NOT NULL,
    combat_progress double precision DEFAULT 0 NOT NULL,
    unclaimed_loot jsonb DEFAULT '[]'::jsonb NOT NULL
);
CREATE TABLE public.incident_event (
    id uuid NOT NULL,
    incident_id uuid NOT NULL,
    kind character varying(32) NOT NULL,
    message character varying(200) NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    data jsonb
);
CREATE TABLE public.incident_participant (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    incident_id uuid NOT NULL,
    dweller_id uuid NOT NULL,
    id uuid NOT NULL
);
CREATE TABLE public.item (
    name character varying(32) NOT NULL,
    rarity public.rarityenum NOT NULL,
    value integer,
    image_url character varying(255),
    id uuid NOT NULL,
    item_type character varying(32) DEFAULT 'misc'::character varying NOT NULL,
    storage_id uuid,
    CONSTRAINT ck_item_item_type CHECK (item_type IN ('misc', 'weapon', 'outfit', 'junk', 'consumable', 'lunchbox', 'pet', 'dweller'))
);
CREATE TABLE public.junk (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(32) NOT NULL,
    rarity public.rarityenum NOT NULL,
    value integer,
    image_url character varying(255),
    junk_type public.junktypeenum NOT NULL,
    description character varying(255) NOT NULL,
    id uuid NOT NULL,
    storage_id uuid
);
CREATE TABLE public.llminteraction (
    parameters character varying,
    response character varying,
    usage character varying,
    prompt_id uuid,
    user_id uuid,
    id uuid NOT NULL,
    created_at timestamp without time zone,
    prompt_tokens integer,
    completion_tokens integer,
    total_tokens integer,
    provider character varying(32),
    model character varying(128),
    instructions_hash character varying(64),
    instructions_snapshot text
);
CREATE TABLE public.notification (
    user_id uuid NOT NULL,
    vault_id uuid,
    from_dweller_id uuid,
    notification_type public.notificationtype NOT NULL,
    priority public.notificationpriority NOT NULL,
    title character varying(200) NOT NULL,
    message character varying(1000) NOT NULL,
    is_read boolean NOT NULL,
    is_dismissed boolean NOT NULL,
    id uuid NOT NULL,
    meta_data json,
    created_at timestamp without time zone NOT NULL,
    read_at timestamp without time zone
);
CREATE TABLE public.objective (
    challenge character varying(32) NOT NULL,
    reward character varying(32) NOT NULL,
    id uuid NOT NULL,
    objective_type character varying,
    target_entity jsonb,
    target_amount integer NOT NULL,
    category character varying(50) DEFAULT 'achievement'::character varying NOT NULL,
    sequence integer,
    description character varying,
    template_key character varying(160),
    assignable boolean DEFAULT true NOT NULL,
    track_key character varying(160)
);
CREATE TABLE public.outfit (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(32) NOT NULL,
    rarity public.rarityenum NOT NULL,
    value integer,
    image_url character varying(255),
    outfit_type public.outfittypeenum,
    gender public.genderenum,
    id uuid NOT NULL,
    dweller_id uuid,
    storage_id uuid,
    fire_resist double precision DEFAULT '0'::double precision NOT NULL,
    radiation_resist double precision,
    strength integer DEFAULT 0 NOT NULL,
    perception integer DEFAULT 0 NOT NULL,
    endurance integer DEFAULT 0 NOT NULL,
    charisma integer DEFAULT 0 NOT NULL,
    intelligence integer DEFAULT 0 NOT NULL,
    agility integer DEFAULT 0 NOT NULL,
    luck integer DEFAULT 0 NOT NULL,
    exploration_id uuid
);
CREATE TABLE public.pet (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(32) NOT NULL,
    rarity public.rarityenum NOT NULL,
    value integer,
    image_url character varying(255),
    id uuid NOT NULL,
    dweller_id uuid,
    storage_id uuid,
    legacy_item_id uuid,
    CONSTRAINT ck_pet_dweller_storage_xor CHECK (((dweller_id IS NULL) OR (storage_id IS NULL)))
);
CREATE TABLE public.pregnancy (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    mother_id uuid,
    father_id uuid,
    conceived_at timestamp without time zone NOT NULL,
    due_at timestamp without time zone NOT NULL,
    status public.pregnancystatusenum NOT NULL,
    id uuid NOT NULL
);
CREATE TABLE public.prompt (
    prompt_name character varying(32) NOT NULL,
    description character varying(1000) NOT NULL,
    prompt_template character varying NOT NULL,
    entity_id uuid,
    id uuid NOT NULL,
    version integer NOT NULL,
    is_active boolean NOT NULL
);
CREATE TABLE public.quest (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    title character varying(64) NOT NULL,
    short_description character varying(128) NOT NULL,
    long_description character varying(500) NOT NULL,
    requirements character varying(500) NOT NULL,
    rewards character varying(500) NOT NULL,
    id uuid NOT NULL,
    quest_type public.questtype NOT NULL,
    quest_category character varying(64),
    chain_id character varying(64),
    chain_order integer NOT NULL,
    previous_quest_id uuid,
    next_quest_id uuid,
    duration_minutes integer DEFAULT 60 NOT NULL
);
CREATE TABLE public.questrequirement (
    requirement_type public.requirementtype NOT NULL,
    requirement_data jsonb NOT NULL,
    is_mandatory boolean NOT NULL,
    id uuid NOT NULL,
    quest_id uuid NOT NULL
);
CREATE TABLE public.questreward (
    reward_type public.rewardtype NOT NULL,
    reward_data jsonb NOT NULL,
    reward_chance double precision NOT NULL,
    id uuid NOT NULL,
    quest_id uuid NOT NULL,
    item_data jsonb
);
CREATE TABLE public.relationship (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    dweller_1_id uuid,
    dweller_2_id uuid,
    relationship_type public.relationshiptypeenum NOT NULL,
    affinity integer NOT NULL,
    id uuid NOT NULL
);
CREATE TABLE public.room (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(32) NOT NULL,
    category public.roomtypeenum NOT NULL,
    ability public.specialenum,
    population_required integer,
    base_cost integer NOT NULL,
    incremental_cost integer,
    t2_upgrade_cost integer,
    t3_upgrade_cost integer,
    capacity integer,
    output integer,
    size_min integer NOT NULL,
    size_max integer NOT NULL,
    size integer,
    tier integer NOT NULL,
    coordinate_x integer,
    coordinate_y integer,
    image_url character varying,
    speedup_multiplier double precision NOT NULL,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    refund_caps integer,
    room_style character varying(16) DEFAULT 'default'::character varying NOT NULL
);
CREATE TABLE public.storage (
    used_space integer NOT NULL,
    max_space integer NOT NULL,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    stimpack integer DEFAULT 0 NOT NULL,
    radaway integer DEFAULT 0 NOT NULL
);
CREATE TABLE public.team (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    quest_id uuid,
    incident_id uuid,
    name character varying(64),
    hazard_team public.hazardteam,
    exploration_id uuid,
    CONSTRAINT ck_team_one_purpose CHECK (((((
CASE
    WHEN (quest_id IS NOT NULL) THEN 1
    ELSE 0
END +
CASE
    WHEN (incident_id IS NOT NULL) THEN 1
    ELSE 0
END) +
CASE
    WHEN (hazard_team IS NOT NULL) THEN 1
    ELSE 0
END) +
CASE
    WHEN (exploration_id IS NOT NULL) THEN 1
    ELSE 0
END) = 1))
);
CREATE TABLE public.team_member (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    id uuid NOT NULL,
    team_id uuid NOT NULL,
    dweller_id uuid NOT NULL,
    slot_number integer,
    status character varying NOT NULL,
    origin_room_id uuid
);
CREATE TABLE public.training (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    dweller_id uuid NOT NULL,
    room_id uuid NOT NULL,
    vault_id uuid NOT NULL,
    stat_being_trained public.specialenum NOT NULL,
    current_stat_value integer NOT NULL,
    target_stat_value integer NOT NULL,
    progress double precision NOT NULL,
    started_at timestamp without time zone NOT NULL,
    estimated_completion_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone,
    status public.trainingstatus NOT NULL,
    id uuid NOT NULL
);
CREATE TABLE public."user" (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    username character varying(32) NOT NULL,
    email character varying,
    is_active boolean NOT NULL,
    is_superuser boolean NOT NULL,
    email_verified boolean NOT NULL,
    email_verification_token character varying,
    password_reset_token character varying,
    password_reset_expires timestamp without time zone,
    id uuid NOT NULL,
    hashed_password character varying NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    monthly_token_limit integer
);
CREATE TABLE public.userprofile (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    bio character varying(500),
    avatar_url character varying(255),
    preferences jsonb,
    total_dwellers_created integer NOT NULL,
    total_caps_earned integer NOT NULL,
    total_explorations integer NOT NULL,
    total_rooms_built integer NOT NULL,
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    total_dwellers_born integer DEFAULT 0 NOT NULL,
    total_dwellers_died integer DEFAULT 0 NOT NULL,
    deaths_by_health integer DEFAULT 0 NOT NULL,
    deaths_by_radiation integer DEFAULT 0 NOT NULL,
    deaths_by_incident integer DEFAULT 0 NOT NULL,
    deaths_by_exploration integer DEFAULT 0 NOT NULL,
    deaths_by_combat integer DEFAULT 0 NOT NULL,
    total_incidents integer DEFAULT 0 NOT NULL,
    total_incidents_won integer DEFAULT 0 NOT NULL,
    total_incidents_lost integer DEFAULT 0 NOT NULL
);
CREATE TABLE public.vault (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    number integer NOT NULL,
    bottle_caps integer NOT NULL,
    happiness integer NOT NULL,
    power integer NOT NULL,
    power_max integer NOT NULL,
    food integer NOT NULL,
    food_max integer NOT NULL,
    water integer NOT NULL,
    water_max integer NOT NULL,
    population_max integer,
    radio_mode character varying(50),
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    incidents_disabled boolean DEFAULT false NOT NULL,
    last_exit_request_at timestamp without time zone,
    arena_morale_awarded_at timestamp without time zone,
    vault_mode character varying(50) DEFAULT 'standard'::character varying NOT NULL
);
CREATE TABLE public.vault_recipe_unlock (
    vault_id uuid NOT NULL,
    item_type character varying(16) NOT NULL,
    recipe_name character varying(128) NOT NULL,
    progress integer NOT NULL,
    unlocked_at timestamp without time zone,
    source character varying(16) NOT NULL
);
CREATE TABLE public.vault_theme (
    vault_id uuid NOT NULL,
    style character varying(16) NOT NULL,
    crafted_at timestamp without time zone,
    source character varying(16) NOT NULL
);
CREATE TABLE public.vaultlocationstate (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    type public.locationtypeenum NOT NULL,
    description character varying(1000),
    id uuid NOT NULL,
    vault_id uuid NOT NULL,
    location_id uuid NOT NULL,
    exploration_id uuid,
    cleared_at timestamp without time zone,
    reclear_available_at timestamp without time zone,
    clear_count integer DEFAULT 0 NOT NULL
);
CREATE TABLE public.vaultobjectiveprogresslink (
    vault_id uuid NOT NULL,
    objective_id uuid NOT NULL,
    progress integer NOT NULL,
    total integer NOT NULL,
    is_completed boolean NOT NULL,
    credited_dweller_ids json DEFAULT '[]'::json NOT NULL,
    reward_snapshot character varying(32),
    is_locked boolean DEFAULT false NOT NULL
);
CREATE TABLE public.vaultquestcompletionlink (
    vault_id uuid NOT NULL,
    quest_id uuid NOT NULL,
    is_completed boolean NOT NULL,
    is_visible boolean NOT NULL,
    started_at timestamp without time zone,
    duration_minutes integer,
    is_reward_ready boolean NOT NULL,
    return_started_at timestamp without time zone,
    return_completes_at timestamp without time zone,
    completed_at timestamp without time zone,
    granted_rewards jsonb
);
CREATE TABLE public.vaultslot (
    id uuid NOT NULL,
    slot_index integer NOT NULL,
    vault_id uuid NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);
CREATE TABLE public.weapon (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(32) NOT NULL,
    rarity public.rarityenum NOT NULL,
    value integer,
    image_url character varying(255),
    weapon_type public.weapontypeenum NOT NULL,
    weapon_subtype public.weaponsubtypeenum NOT NULL,
    stat character varying NOT NULL,
    damage_min integer NOT NULL,
    damage_max integer NOT NULL,
    id uuid NOT NULL,
    dweller_id uuid,
    storage_id uuid,
    exploration_id uuid
);
CREATE TABLE public.worldlocation (
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    name character varying(64) NOT NULL,
    normalized_name character varying(64) NOT NULL,
    vault_number integer,
    coord_x double precision NOT NULL,
    coord_y double precision NOT NULL,
    description character varying(1000),
    source character varying(16) NOT NULL,
    id uuid NOT NULL,
    kind public.placekind NOT NULL,
    group_key character varying(32),
    CONSTRAINT ck_world_location_coord_x_range CHECK (((coord_x >= (0)::double precision) AND (coord_x <= (100)::double precision))),
    CONSTRAINT ck_world_location_coord_y_range CHECK (((coord_y >= (0)::double precision) AND (coord_y <= (100)::double precision))),
    CONSTRAINT ck_world_location_kind_fields CHECK ((((kind = 'VAULT'::public.placekind) AND (vault_number IS NOT NULL)) OR ((kind = 'PLACE'::public.placekind) AND (vault_number IS NULL))))
);
CREATE TABLE public.worldsnapshot (
    id uuid NOT NULL,
    world_id character varying(32) NOT NULL,
    generator_version integer NOT NULL,
    seed character varying(64) NOT NULL,
    config jsonb NOT NULL,
    recipe_fingerprint character varying(64) NOT NULL,
    snapshot_checksum character varying(64) NOT NULL,
    terrain jsonb NOT NULL,
    slots jsonb NOT NULL,
    anchors jsonb NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);
ALTER TABLE ONLY public.ai_settings
    ADD CONSTRAINT ai_settings_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.arena_match_event
    ADD CONSTRAINT arena_match_event_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.craftingorder
    ADD CONSTRAINT craftingorder_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.dwellerlocation
    ADD CONSTRAINT dwellerlocation_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.expeditionrun
    ADD CONSTRAINT expeditionrun_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.exploration
    ADD CONSTRAINT exploration_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.gamestate
    ADD CONSTRAINT gamestate_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.incident_event
    ADD CONSTRAINT incident_event_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.incident_participant
    ADD CONSTRAINT incident_participant_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.incident
    ADD CONSTRAINT incident_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.item
    ADD CONSTRAINT item_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.junk
    ADD CONSTRAINT junk_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.llminteraction
    ADD CONSTRAINT llminteraction_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.objective
    ADD CONSTRAINT objective_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.outfit
    ADD CONSTRAINT outfit_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.pet
    ADD CONSTRAINT pet_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT pk_arena_state PRIMARY KEY (room_id);
ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.prompt
    ADD CONSTRAINT prompt_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.quest
    ADD CONSTRAINT quest_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.questrequirement
    ADD CONSTRAINT questrequirement_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.questreward
    ADD CONSTRAINT questreward_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.storage
    ADD CONSTRAINT storage_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT team_member_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT team_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.training
    ADD CONSTRAINT training_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.dwellerlocation
    ADD CONSTRAINT uq_dweller_location_relation UNIQUE (dweller_id, location_id, relation);
ALTER TABLE ONLY public.incident_participant
    ADD CONSTRAINT uq_incident_participant UNIQUE (incident_id, dweller_id);
ALTER TABLE ONLY public.prompt
    ADD CONSTRAINT uq_prompt_name_version UNIQUE (prompt_name, version);
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT uq_team_member_dweller UNIQUE (team_id, dweller_id);
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT uq_team_member_slot UNIQUE (team_id, slot_number);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT uq_team_vault_exploration UNIQUE (vault_id, exploration_id);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT uq_team_vault_hazard UNIQUE (vault_id, hazard_team);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT uq_team_vault_incident UNIQUE (vault_id, incident_id);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT uq_team_vault_quest UNIQUE (vault_id, quest_id);
ALTER TABLE ONLY public.vaultlocationstate
    ADD CONSTRAINT uq_vault_location_state UNIQUE (vault_id, location_id);
ALTER TABLE ONLY public.vaultslot
    ADD CONSTRAINT uq_vault_slot_index UNIQUE (slot_index);
ALTER TABLE ONLY public.vaultslot
    ADD CONSTRAINT uq_vault_slot_vault UNIQUE (vault_id);
ALTER TABLE ONLY public.worldsnapshot
    ADD CONSTRAINT uq_worldsnapshot_world_version UNIQUE (world_id, generator_version);
ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.userprofile
    ADD CONSTRAINT userprofile_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.vault
    ADD CONSTRAINT vault_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.vault_recipe_unlock
    ADD CONSTRAINT vault_recipe_unlock_pkey PRIMARY KEY (vault_id, item_type, recipe_name);
ALTER TABLE ONLY public.vault_theme
    ADD CONSTRAINT vault_theme_pkey PRIMARY KEY (vault_id, style);
ALTER TABLE ONLY public.vaultlocationstate
    ADD CONSTRAINT vaultlocationstate_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.vaultobjectiveprogresslink
    ADD CONSTRAINT vaultobjectiveprogresslink_pkey PRIMARY KEY (vault_id, objective_id);
ALTER TABLE ONLY public.vaultquestcompletionlink
    ADD CONSTRAINT vaultquestcompletionlink_pkey PRIMARY KEY (vault_id, quest_id);
ALTER TABLE ONLY public.vaultslot
    ADD CONSTRAINT vaultslot_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.weapon
    ADD CONSTRAINT weapon_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.worldlocation
    ADD CONSTRAINT worldlocation_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.worldsnapshot
    ADD CONSTRAINT worldsnapshot_pkey PRIMARY KEY (id);
CREATE INDEX ix_ai_settings_id ON public.ai_settings USING btree (id);
CREATE INDEX ix_arena_match_event_kind ON public.arena_match_event USING btree (kind);
CREATE INDEX ix_arena_match_event_room_id ON public.arena_match_event USING btree (room_id);
CREATE INDEX ix_arena_state_fighter_a_id ON public.arena_state USING btree (fighter_a_id);
CREATE INDEX ix_arena_state_fighter_b_id ON public.arena_state USING btree (fighter_b_id);
CREATE INDEX ix_arena_state_fighter_c_id ON public.arena_state USING btree (fighter_c_id);
CREATE INDEX ix_arena_state_fighter_d_id ON public.arena_state USING btree (fighter_d_id);
CREATE INDEX ix_chatmessage_created_at ON public.chatmessage USING btree (created_at);
CREATE INDEX ix_chatmessage_from_dweller_id ON public.chatmessage USING btree (from_dweller_id);
CREATE INDEX ix_chatmessage_from_user_id ON public.chatmessage USING btree (from_user_id);
CREATE INDEX ix_chatmessage_id ON public.chatmessage USING btree (id);
CREATE INDEX ix_chatmessage_to_dweller_id ON public.chatmessage USING btree (to_dweller_id);
CREATE INDEX ix_chatmessage_to_user_id ON public.chatmessage USING btree (to_user_id);
CREATE INDEX ix_chatmessage_vault_id ON public.chatmessage USING btree (vault_id);
CREATE INDEX ix_craftingorder_id ON public.craftingorder USING btree (id);
CREATE INDEX ix_craftingorder_room_id ON public.craftingorder USING btree (room_id);
CREATE INDEX ix_craftingorder_status ON public.craftingorder USING btree (status);
CREATE INDEX ix_craftingorder_vault_id ON public.craftingorder USING btree (vault_id);
CREATE INDEX ix_dweller_availability ON public.dweller USING btree (availability);
CREATE INDEX ix_dweller_first_name ON public.dweller USING btree (first_name);
CREATE INDEX ix_dweller_id ON public.dweller USING btree (id);
CREATE INDEX ix_dweller_is_dead ON public.dweller USING btree (is_dead);
CREATE INDEX ix_dweller_is_deleted ON public.dweller USING btree (is_deleted);
CREATE INDEX ix_dweller_is_permanently_dead ON public.dweller USING btree (is_permanently_dead);
CREATE INDEX ix_dweller_last_name ON public.dweller USING btree (last_name);
CREATE INDEX ix_dweller_lifecycle ON public.dweller USING btree (lifecycle);
CREATE INDEX ix_dweller_room_id ON public.dweller USING btree (room_id);
CREATE INDEX ix_dweller_status ON public.dweller USING btree (status);
CREATE INDEX ix_dweller_vault_id ON public.dweller USING btree (vault_id);
CREATE INDEX ix_dwellerlocation_dweller_id ON public.dwellerlocation USING btree (dweller_id);
CREATE INDEX ix_dwellerlocation_id ON public.dwellerlocation USING btree (id);
CREATE INDEX ix_dwellerlocation_location_id ON public.dwellerlocation USING btree (location_id);
CREATE INDEX ix_expeditionrun_exploration_id ON public.expeditionrun USING btree (exploration_id);
CREATE INDEX ix_expeditionrun_id ON public.expeditionrun USING btree (id);
CREATE INDEX ix_expeditionrun_site_id ON public.expeditionrun USING btree (site_id);
CREATE INDEX ix_expeditionrun_status ON public.expeditionrun USING btree (status);
CREATE INDEX ix_expeditionrun_vault_id ON public.expeditionrun USING btree (vault_id);
CREATE INDEX ix_exploration_dweller_id ON public.exploration USING btree (dweller_id);
CREATE INDEX ix_exploration_id ON public.exploration USING btree (id);
CREATE INDEX ix_exploration_status ON public.exploration USING btree (status);
CREATE INDEX ix_exploration_team_id ON public.exploration USING btree (team_id);
CREATE INDEX ix_exploration_vault_id ON public.exploration USING btree (vault_id);
CREATE INDEX ix_gamestate_id ON public.gamestate USING btree (id);
CREATE UNIQUE INDEX ix_gamestate_vault_id ON public.gamestate USING btree (vault_id);
CREATE INDEX ix_incident_event_incident_id ON public.incident_event USING btree (incident_id);
CREATE INDEX ix_incident_event_kind ON public.incident_event USING btree (kind);
CREATE INDEX ix_incident_id ON public.incident USING btree (id);
CREATE INDEX ix_incident_participant_dweller_id ON public.incident_participant USING btree (dweller_id);
CREATE INDEX ix_incident_participant_id ON public.incident_participant USING btree (id);
CREATE INDEX ix_incident_participant_incident_id ON public.incident_participant USING btree (incident_id);
CREATE INDEX ix_incident_room_id ON public.incident USING btree (room_id);
CREATE INDEX ix_incident_status ON public.incident USING btree (status);
CREATE INDEX ix_incident_type ON public.incident USING btree (type);
CREATE INDEX ix_incident_vault_id ON public.incident USING btree (vault_id);
CREATE INDEX ix_item_id ON public.item USING btree (id);
CREATE INDEX ix_item_name ON public.item USING btree (name);
CREATE INDEX ix_junk_id ON public.junk USING btree (id);
CREATE INDEX ix_junk_name ON public.junk USING btree (name);
CREATE INDEX ix_llminteraction_id ON public.llminteraction USING btree (id);
CREATE INDEX ix_llminteraction_user_id ON public.llminteraction USING btree (user_id);
CREATE INDEX ix_notification_created_at ON public.notification USING btree (created_at);
CREATE INDEX ix_notification_from_dweller_id ON public.notification USING btree (from_dweller_id);
CREATE INDEX ix_notification_id ON public.notification USING btree (id);
CREATE INDEX ix_notification_is_dismissed ON public.notification USING btree (is_dismissed);
CREATE INDEX ix_notification_is_read ON public.notification USING btree (is_read);
CREATE INDEX ix_notification_notification_type ON public.notification USING btree (notification_type);
CREATE INDEX ix_notification_priority ON public.notification USING btree (priority);
CREATE INDEX ix_notification_user_id ON public.notification USING btree (user_id);
CREATE INDEX ix_notification_vault_id ON public.notification USING btree (vault_id);
CREATE INDEX ix_objective_assignable ON public.objective USING btree (assignable);
CREATE INDEX ix_objective_category ON public.objective USING btree (category);
CREATE INDEX ix_objective_challenge ON public.objective USING btree (challenge);
CREATE INDEX ix_objective_id ON public.objective USING btree (id);
CREATE INDEX ix_objective_objective_type ON public.objective USING btree (objective_type);
CREATE INDEX ix_objective_sequence ON public.objective USING btree (sequence);
CREATE UNIQUE INDEX ix_objective_template_key ON public.objective USING btree (template_key);
CREATE INDEX ix_objective_track_key ON public.objective USING btree (track_key);
CREATE UNIQUE INDEX ix_objective_track_stage ON public.objective USING btree (track_key, sequence);
CREATE INDEX ix_outfit_dweller_id ON public.outfit USING btree (dweller_id);
CREATE INDEX ix_outfit_exploration_id ON public.outfit USING btree (exploration_id);
CREATE INDEX ix_outfit_id ON public.outfit USING btree (id);
CREATE INDEX ix_outfit_name ON public.outfit USING btree (name);
CREATE INDEX ix_pet_dweller_id ON public.pet USING btree (dweller_id);
CREATE INDEX ix_pet_id ON public.pet USING btree (id);
CREATE UNIQUE INDEX ix_pet_legacy_item_id ON public.pet USING btree (legacy_item_id);
CREATE INDEX ix_pet_name ON public.pet USING btree (name);
CREATE INDEX ix_pet_storage_id ON public.pet USING btree (storage_id);
CREATE INDEX ix_pregnancy_father_id ON public.pregnancy USING btree (father_id);
CREATE INDEX ix_pregnancy_id ON public.pregnancy USING btree (id);
CREATE INDEX ix_pregnancy_mother_id ON public.pregnancy USING btree (mother_id);
CREATE UNIQUE INDEX ix_prompt_active_name ON public.prompt USING btree (prompt_name) WHERE (is_active = true);
CREATE INDEX ix_prompt_entity_id ON public.prompt USING btree (entity_id);
CREATE INDEX ix_prompt_id ON public.prompt USING btree (id);
CREATE INDEX ix_prompt_is_active ON public.prompt USING btree (is_active);
CREATE INDEX ix_prompt_prompt_name ON public.prompt USING btree (prompt_name);
CREATE INDEX ix_quest_chain_id ON public.quest USING btree (chain_id);
CREATE INDEX ix_quest_id ON public.quest USING btree (id);
CREATE INDEX ix_quest_quest_category ON public.quest USING btree (quest_category);
CREATE INDEX ix_quest_quest_type ON public.quest USING btree (quest_type);
CREATE INDEX ix_quest_title ON public.quest USING btree (title);
CREATE INDEX ix_questrequirement_id ON public.questrequirement USING btree (id);
CREATE INDEX ix_questrequirement_quest_id ON public.questrequirement USING btree (quest_id);
CREATE INDEX ix_questrequirement_requirement_type ON public.questrequirement USING btree (requirement_type);
CREATE INDEX ix_questreward_id ON public.questreward USING btree (id);
CREATE INDEX ix_questreward_quest_id ON public.questreward USING btree (quest_id);
CREATE INDEX ix_questreward_reward_type ON public.questreward USING btree (reward_type);
CREATE INDEX ix_relationship_dweller_1_id ON public.relationship USING btree (dweller_1_id);
CREATE INDEX ix_relationship_dweller_2_id ON public.relationship USING btree (dweller_2_id);
CREATE INDEX ix_relationship_id ON public.relationship USING btree (id);
CREATE INDEX ix_room_id ON public.room USING btree (id);
CREATE INDEX ix_room_name ON public.room USING btree (name);
CREATE INDEX ix_room_vault_id ON public.room USING btree (vault_id);
CREATE INDEX ix_storage_id ON public.storage USING btree (id);
CREATE INDEX ix_storage_vault_id ON public.storage USING btree (vault_id);
CREATE INDEX ix_team_exploration_id ON public.team USING btree (exploration_id);
CREATE INDEX ix_team_hazard_team ON public.team USING btree (hazard_team);
CREATE INDEX ix_team_id ON public.team USING btree (id);
CREATE INDEX ix_team_incident_id ON public.team USING btree (incident_id);
CREATE INDEX ix_team_member_dweller_id ON public.team_member USING btree (dweller_id);
CREATE INDEX ix_team_member_id ON public.team_member USING btree (id);
CREATE INDEX ix_team_member_team_id ON public.team_member USING btree (team_id);
CREATE INDEX ix_team_quest_id ON public.team USING btree (quest_id);
CREATE INDEX ix_team_vault_id ON public.team USING btree (vault_id);
CREATE INDEX ix_training_dweller_id ON public.training USING btree (dweller_id);
CREATE INDEX ix_training_id ON public.training USING btree (id);
CREATE INDEX ix_training_room_id ON public.training USING btree (room_id);
CREATE INDEX ix_training_status ON public.training USING btree (status);
CREATE INDEX ix_training_vault_id ON public.training USING btree (vault_id);
CREATE UNIQUE INDEX ix_user_email ON public."user" USING btree (email);
CREATE INDEX ix_user_email_verification_token ON public."user" USING btree (email_verification_token);
CREATE INDEX ix_user_id ON public."user" USING btree (id);
CREATE INDEX ix_user_is_deleted ON public."user" USING btree (is_deleted);
CREATE INDEX ix_user_password_reset_token ON public."user" USING btree (password_reset_token);
CREATE UNIQUE INDEX ix_user_username ON public."user" USING btree (username);
CREATE INDEX ix_userprofile_id ON public.userprofile USING btree (id);
CREATE UNIQUE INDEX ix_userprofile_user_id ON public.userprofile USING btree (user_id);
CREATE INDEX ix_vault_id ON public.vault USING btree (id);
CREATE INDEX ix_vault_is_deleted ON public.vault USING btree (is_deleted);
CREATE INDEX ix_vault_number ON public.vault USING btree (number);
CREATE INDEX ix_vault_user_id ON public.vault USING btree (user_id);
CREATE INDEX ix_vaultlocationstate_id ON public.vaultlocationstate USING btree (id);
CREATE INDEX ix_vaultlocationstate_location_id ON public.vaultlocationstate USING btree (location_id);
CREATE INDEX ix_vaultlocationstate_vault_id ON public.vaultlocationstate USING btree (vault_id);
CREATE INDEX ix_vaultslot_id ON public.vaultslot USING btree (id);
CREATE INDEX ix_weapon_dweller_id ON public.weapon USING btree (dweller_id);
CREATE INDEX ix_weapon_exploration_id ON public.weapon USING btree (exploration_id);
CREATE INDEX ix_weapon_id ON public.weapon USING btree (id);
CREATE INDEX ix_weapon_name ON public.weapon USING btree (name);
CREATE INDEX ix_worldlocation_group_key ON public.worldlocation USING btree (group_key);
CREATE INDEX ix_worldlocation_id ON public.worldlocation USING btree (id);
CREATE UNIQUE INDEX ix_worldlocation_normalized_name ON public.worldlocation USING btree (normalized_name);
CREATE INDEX ix_worldsnapshot_id ON public.worldsnapshot USING btree (id);
CREATE INDEX ix_worldsnapshot_recipe_fingerprint ON public.worldsnapshot USING btree (recipe_fingerprint);
CREATE INDEX ix_worldsnapshot_world_id ON public.worldsnapshot USING btree (world_id);
CREATE UNIQUE INDEX uq_dweller_active_apprentice_room ON public.dweller USING btree (room_id) WHERE ((apprentice_started_at IS NOT NULL) AND (is_deleted = false));
CREATE UNIQUE INDEX uq_expeditionrun_open_exploration ON public.expeditionrun USING btree (exploration_id) WHERE (status = 'IN_ROOM'::public.expeditionrunstatus);
CREATE UNIQUE INDEX uq_expeditionrun_open_vault_site ON public.expeditionrun USING btree (vault_id, site_id) WHERE (status = 'IN_ROOM'::public.expeditionrunstatus);
CREATE UNIQUE INDEX uq_world_location_vault_number ON public.worldlocation USING btree (vault_number) WHERE (kind = 'VAULT'::public.placekind);
ALTER TABLE ONLY public.arena_match_event
    ADD CONSTRAINT arena_match_event_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_from_dweller_id_fkey FOREIGN KEY (from_dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_from_user_id_fkey FOREIGN KEY (from_user_id) REFERENCES public."user"(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_llm_interaction_id_fkey FOREIGN KEY (llm_interaction_id) REFERENCES public.llminteraction(id);
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_to_dweller_id_fkey FOREIGN KEY (to_dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES public."user"(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.craftingorder
    ADD CONSTRAINT craftingorder_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id);
ALTER TABLE ONLY public.craftingorder
    ADD CONSTRAINT craftingorder_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_parent_1_id_fkey FOREIGN KEY (parent_1_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_parent_2_id_fkey FOREIGN KEY (parent_2_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_partner_id_fkey FOREIGN KEY (partner_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_previous_vault_id_fkey FOREIGN KEY (previous_vault_id) REFERENCES public.vault(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.dweller
    ADD CONSTRAINT dweller_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.dwellerlocation
    ADD CONSTRAINT dwellerlocation_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.expeditionrun
    ADD CONSTRAINT expeditionrun_exploration_id_fkey FOREIGN KEY (exploration_id) REFERENCES public.exploration(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.expeditionrun
    ADD CONSTRAINT expeditionrun_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.exploration
    ADD CONSTRAINT exploration_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.exploration
    ADD CONSTRAINT exploration_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT fk_arena_state_fighter_a_id FOREIGN KEY (fighter_a_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT fk_arena_state_fighter_b_id FOREIGN KEY (fighter_b_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT fk_arena_state_fighter_c_id FOREIGN KEY (fighter_c_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT fk_arena_state_fighter_d_id FOREIGN KEY (fighter_d_id) REFERENCES public.dweller(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.arena_state
    ADD CONSTRAINT fk_arena_state_room_id FOREIGN KEY (room_id) REFERENCES public.room(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.dwellerlocation
    ADD CONSTRAINT fk_dwellerlocation_location_id_worldlocation FOREIGN KEY (location_id) REFERENCES public.worldlocation(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.exploration
    ADD CONSTRAINT fk_exploration_target_location_id FOREIGN KEY (target_location_id) REFERENCES public.worldlocation(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.exploration
    ADD CONSTRAINT fk_exploration_team_id FOREIGN KEY (team_id) REFERENCES public.team(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.item
    ADD CONSTRAINT fk_item_storage_id_storage FOREIGN KEY (storage_id) REFERENCES public.storage(id);
ALTER TABLE ONLY public.outfit
    ADD CONSTRAINT fk_outfit_exploration_id_exploration FOREIGN KEY (exploration_id) REFERENCES public.exploration(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.quest
    ADD CONSTRAINT fk_quest_next_quest_id FOREIGN KEY (next_quest_id) REFERENCES public.quest(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.quest
    ADD CONSTRAINT fk_quest_previous_quest_id FOREIGN KEY (previous_quest_id) REFERENCES public.quest(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT fk_team_member_origin_room_id FOREIGN KEY (origin_room_id) REFERENCES public.room(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.weapon
    ADD CONSTRAINT fk_weapon_exploration_id_exploration FOREIGN KEY (exploration_id) REFERENCES public.exploration(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.gamestate
    ADD CONSTRAINT gamestate_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.incident_event
    ADD CONSTRAINT incident_event_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incident(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.incident_participant
    ADD CONSTRAINT incident_participant_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.incident_participant
    ADD CONSTRAINT incident_participant_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incident(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.incident
    ADD CONSTRAINT incident_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.incident
    ADD CONSTRAINT incident_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.junk
    ADD CONSTRAINT junk_storage_id_fkey FOREIGN KEY (storage_id) REFERENCES public.storage(id);
ALTER TABLE ONLY public.llminteraction
    ADD CONSTRAINT llminteraction_prompt_id_fkey FOREIGN KEY (prompt_id) REFERENCES public.prompt(id);
ALTER TABLE ONLY public.llminteraction
    ADD CONSTRAINT llminteraction_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_from_dweller_id_fkey FOREIGN KEY (from_dweller_id) REFERENCES public.dweller(id);
ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.outfit
    ADD CONSTRAINT outfit_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id);
ALTER TABLE ONLY public.outfit
    ADD CONSTRAINT outfit_storage_id_fkey FOREIGN KEY (storage_id) REFERENCES public.storage(id);
ALTER TABLE ONLY public.pet
    ADD CONSTRAINT pet_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id);
ALTER TABLE ONLY public.pet
    ADD CONSTRAINT pet_storage_id_fkey FOREIGN KEY (storage_id) REFERENCES public.storage(id);
ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_father_id_fkey FOREIGN KEY (father_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.pregnancy
    ADD CONSTRAINT pregnancy_mother_id_fkey FOREIGN KEY (mother_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.questrequirement
    ADD CONSTRAINT questrequirement_quest_id_fkey FOREIGN KEY (quest_id) REFERENCES public.quest(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.questreward
    ADD CONSTRAINT questreward_quest_id_fkey FOREIGN KEY (quest_id) REFERENCES public.quest(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_dweller_1_id_fkey FOREIGN KEY (dweller_1_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_dweller_2_id_fkey FOREIGN KEY (dweller_2_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.storage
    ADD CONSTRAINT storage_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT team_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incident(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT team_member_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.team_member
    ADD CONSTRAINT team_member_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.team(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.team
    ADD CONSTRAINT team_quest_id_fkey FOREIGN KEY (quest_id) REFERENCES public.quest(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.team
    ADD CONSTRAINT team_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.training
    ADD CONSTRAINT training_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id);
ALTER TABLE ONLY public.training
    ADD CONSTRAINT training_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id);
ALTER TABLE ONLY public.training
    ADD CONSTRAINT training_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.userprofile
    ADD CONSTRAINT userprofile_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.vault_recipe_unlock
    ADD CONSTRAINT vault_recipe_unlock_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.vault_theme
    ADD CONSTRAINT vault_theme_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.vault
    ADD CONSTRAINT vault_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
ALTER TABLE ONLY public.vaultlocationstate
    ADD CONSTRAINT vaultlocationstate_exploration_id_fkey FOREIGN KEY (exploration_id) REFERENCES public.exploration(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.vaultlocationstate
    ADD CONSTRAINT vaultlocationstate_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.worldlocation(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.vaultlocationstate
    ADD CONSTRAINT vaultlocationstate_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.vaultobjectiveprogresslink
    ADD CONSTRAINT vaultobjectiveprogresslink_objective_id_fkey FOREIGN KEY (objective_id) REFERENCES public.objective(id);
ALTER TABLE ONLY public.vaultobjectiveprogresslink
    ADD CONSTRAINT vaultobjectiveprogresslink_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.vaultquestcompletionlink
    ADD CONSTRAINT vaultquestcompletionlink_quest_id_fkey FOREIGN KEY (quest_id) REFERENCES public.quest(id);
ALTER TABLE ONLY public.vaultquestcompletionlink
    ADD CONSTRAINT vaultquestcompletionlink_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id);
ALTER TABLE ONLY public.vaultslot
    ADD CONSTRAINT vaultslot_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.vault(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.weapon
    ADD CONSTRAINT weapon_dweller_id_fkey FOREIGN KEY (dweller_id) REFERENCES public.dweller(id);
ALTER TABLE ONLY public.weapon
    ADD CONSTRAINT weapon_storage_id_fkey FOREIGN KEY (storage_id) REFERENCES public.storage(id);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 2000 Caps', '200 caps', 'b495d3f8-abca-4be6-8e5b-e868c010aae0', 'collect', '{"resource_type": "caps"}', 2000, 'weekly', NULL, NULL, 'weekly:collect 2000 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 3000 Caps', '300 caps', '1e5bebcf-1b30-4b45-9059-5efaae1376cd', 'collect', '{"resource_type": "caps"}', 3000, 'weekly', NULL, NULL, 'weekly:collect 3000 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 5000 Caps', '500 caps', '47e1613b-6f8e-4485-b7db-51a8bf1d44c8', 'collect', '{"resource_type": "caps"}', 5000, 'weekly', NULL, NULL, 'weekly:collect 5000 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 1000 Food', '100 caps', '67d6cc9d-cbd6-4409-a9e7-69ba2d39caf2', 'collect', '{"resource_type": "food", "production_only": true}', 1000, 'weekly', NULL, NULL, 'weekly:collect 1000 food', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 2000 Food', '200 caps', '569e479d-da54-4ccb-874e-faae58287ed0', 'collect', '{"resource_type": "food", "production_only": true}', 2000, 'weekly', NULL, NULL, 'weekly:collect 2000 food', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 1000 Water', '100 caps', '5454b4aa-f877-494c-89a6-6a211dc4e021', 'collect', '{"resource_type": "water", "production_only": true}', 1000, 'weekly', NULL, NULL, 'weekly:collect 1000 water', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 2000 Water', '200 caps', 'dc8bf8ba-efd9-429c-9c01-b5861be95ba9', 'collect', '{"resource_type": "water", "production_only": true}', 2000, 'weekly', NULL, NULL, 'weekly:collect 2000 water', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 1000 Power', '100 caps', 'c93ebefe-be7b-4aa3-a04a-ed2caa789522', 'collect', '{"resource_type": "power", "production_only": true}', 1000, 'weekly', NULL, NULL, 'weekly:collect 1000 power', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 2000 Power', '200 caps', 'f147c9a5-36f3-42c7-817e-ae8248cc8aef', 'collect', '{"resource_type": "power", "production_only": true}', 2000, 'weekly', NULL, NULL, 'weekly:collect 2000 power', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 5 Rooms', '125 caps', 'e646d614-2b34-4de3-8203-dc7cf98d8254', 'build', '{"room_type": "*"}', 5, 'weekly', NULL, NULL, 'weekly:build 5 rooms', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 7 Rooms', '175 caps', '08151609-c180-487a-8931-010e12b2acda', 'build', '{"room_type": "*"}', 7, 'weekly', NULL, NULL, 'weekly:build 7 rooms', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 10 Rooms', '250 caps', '18fa375d-8ae6-4cc5-8668-e3c076a7c997', 'build', '{"room_type": "*"}', 10, 'weekly', NULL, NULL, 'weekly:build 10 rooms', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 5 Dwellers', '100 caps', '5a012ca8-2255-4567-86a2-e9e2254461d1', 'assign', '{"distinct_dwellers": true}', 5, 'weekly', NULL, NULL, 'weekly:assign 5 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 8 Dwellers', '160 caps', '5eb0a6fd-c8f5-48f3-98db-834514f3af59', 'assign', '{"distinct_dwellers": true}', 8, 'weekly', NULL, NULL, 'weekly:assign 8 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 10 Dwellers', '200 caps', 'eb56f36c-4ac4-430d-9d68-544828ef39c6', 'assign', '{"distinct_dwellers": true}', 10, 'weekly', NULL, NULL, 'weekly:assign 10 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 5 Dwellers', '125 caps', 'fb08e88f-9bc8-4c58-a20b-5fee97a50628', 'assign_correct', '{"distinct_dwellers": true}', 5, 'weekly', NULL, NULL, 'weekly:correctly assign 5 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 8 Dwellers', '200 caps', '81febdb2-ab95-456c-8858-fb1309695cbc', 'assign_correct', '{"distinct_dwellers": true}', 8, 'weekly', NULL, NULL, 'weekly:correctly assign 8 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train 3 Dwellers', '150 caps', '757f3c53-a850-4141-9c4d-f13e9724a624', 'train', '{"distinct_dwellers": true}', 3, 'weekly', NULL, NULL, 'weekly:train 3 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train 5 Dwellers', '250 caps', '4e716c8a-f210-434e-97e3-c0af7ed089a1', 'train', '{"distinct_dwellers": true}', 5, 'weekly', NULL, NULL, 'weekly:train 5 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Level up 2 Dwellers to Lv.5', '150 caps', '67023811-a90e-4a21-82b5-f51f8bb4cfd3', 'level_up', '{"min_level": 5, "distinct_dwellers": true}', 2, 'weekly', NULL, NULL, 'weekly:level up 2 dwellers to lv.5', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Level up 3 Dwellers to Lv.5', '225 caps', '71e981cf-6ddb-4a6d-b0ba-cca281911c9a', 'level_up', '{"min_level": 5, "distinct_dwellers": true}', 3, 'weekly', NULL, NULL, 'weekly:level up 3 dwellers to lv.5', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Level up 2 Dwellers to Lv.10', '150 caps', '9a7bb98c-8983-45f4-9bd8-d3b8b1fa86df', 'level_up', '{"min_level": 10, "distinct_dwellers": true}', 2, 'weekly', NULL, NULL, 'weekly:level up 2 dwellers to lv.10', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 30 Dwellers', '300 caps', '8ffd879a-ab0d-45f5-96cd-af8678cc8cce', 'reach', '{"reach_type": "dweller_count"}', 30, 'weekly', NULL, NULL, 'weekly:reach 30 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 2 Quests', '200 caps', '59f368ea-7c0a-4ba0-904c-a4e3636cd731', 'expedition', '{}', 2, 'weekly', NULL, NULL, 'weekly:complete 2 expeditions', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 3 Quests', '300 caps', 'b75dbf87-43d0-43ab-8de4-86b80a1ff004', 'expedition', '{}', 3, 'weekly', NULL, NULL, 'weekly:complete 3 expeditions', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 1 Main Quest', '150 caps', '8be30a50-be1e-486e-9d31-16b94b60cbff', 'expedition', '{"quest_type": "main"}', 1, 'weekly', NULL, NULL, 'weekly:complete 1 main quest', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 200 Caps', '20 caps', '24a0c042-bc18-45be-8c3b-98b825afea48', 'collect', '{"resource_type": "caps"}', 200, 'daily', NULL, NULL, 'daily:collect 200 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 300 Caps', '30 caps', '41f4b96c-38fe-463d-9b32-477f00d2b99f', 'collect', '{"resource_type": "caps"}', 300, 'daily', NULL, NULL, 'daily:collect 300 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 500 Caps', '50 caps', '415e61a7-07ec-4a49-a09e-f81a7335618e', 'collect', '{"resource_type": "caps"}', 500, 'daily', NULL, NULL, 'daily:collect 500 caps', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 150 Food', '25 caps', '120d016c-932c-47ca-b5b9-f5bd60ff2864', 'collect', '{"resource_type": "food", "production_only": true}', 150, 'daily', NULL, NULL, 'daily:collect 150 food', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 250 Food', '40 caps', 'd509b967-255d-4073-8256-c8f71d52e2e9', 'collect', '{"resource_type": "food", "production_only": true}', 250, 'daily', NULL, NULL, 'daily:collect 250 food', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 150 Water', '25 caps', 'd7d766b8-53bf-4293-b1ba-6d44291ea02e', 'collect', '{"resource_type": "water", "production_only": true}', 150, 'daily', NULL, NULL, 'daily:collect 150 water', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 250 Water', '40 caps', 'f52b2e8e-39a2-43eb-a852-fbb3a82f11be', 'collect', '{"resource_type": "water", "production_only": true}', 250, 'daily', NULL, NULL, 'daily:collect 250 water', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 150 Power', '25 caps', 'e7b9a5bd-4117-4ba5-93c7-2304aa6db28d', 'collect', '{"resource_type": "power", "production_only": true}', 150, 'daily', NULL, NULL, 'daily:collect 150 power', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 250 Power', '40 caps', 'def68aab-cda6-44ae-beb6-723940df2dec', 'collect', '{"resource_type": "power", "production_only": true}', 250, 'daily', NULL, NULL, 'daily:collect 250 power', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 3 Weapons', 'weapon:Pipe Pistol', '6068513c-1da1-4de7-847a-cfd6d706f282', 'collect', '{"item_type": "weapon"}', 3, 'daily', NULL, NULL, 'daily:collect 3 weapons', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 3 Outfits', 'outfit:Mechanic jumpsuit', 'c4611462-8015-4004-8a25-9777f36df8a7', 'collect', '{"item_type": "outfit"}', 3, 'daily', NULL, NULL, 'daily:collect 3 outfits', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 2 Rooms', '50 caps', '7363d10e-0e97-40f2-bb69-353de3fbd286', 'build', '{"room_type": "*"}', 2, 'daily', NULL, NULL, 'daily:build 2 rooms', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 3 Rooms', '75 caps', '3ea6a555-21ff-4322-884f-f4d0ef21d44f', 'build', '{"room_type": "*"}', 3, 'daily', NULL, NULL, 'daily:build 3 rooms', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 2 Dwellers', '40 caps', 'feec0a66-04d9-49c1-a94e-6f22e4a06173', 'assign', '{"distinct_dwellers": true}', 2, 'daily', NULL, NULL, 'daily:assign 2 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 3 Dwellers', '60 caps', '88820d80-744a-4e01-ba4b-c22e20bb2093', 'assign', '{"distinct_dwellers": true}', 3, 'daily', NULL, NULL, 'daily:assign 3 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 4 Dwellers', '80 caps', 'cd4d779d-e251-468e-b698-70cf7b5dc8f9', 'assign', '{"distinct_dwellers": true}', 4, 'daily', NULL, NULL, 'daily:assign 4 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 2 Dwellers', '50 caps', '957328dd-b084-466c-b6b8-1112b2f8906f', 'assign_correct', '{"distinct_dwellers": true}', 2, 'daily', NULL, NULL, 'daily:correctly assign 2 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 3 Dwellers', '75 caps', '2ff4c034-5162-4af4-aeca-f48658ed936f', 'assign_correct', '{"distinct_dwellers": true}', 3, 'daily', NULL, NULL, 'daily:correctly assign 3 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train 1 Dweller', '50 caps', '3a9f99cd-2c05-4637-85a3-8678498a7a6a', 'train', '{"distinct_dwellers": true}', 1, 'daily', NULL, NULL, 'daily:train 1 dweller', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train 2 Dwellers', '100 caps', '22eeeff9-e81e-4e00-b234-3e87b519add1', 'train', '{"distinct_dwellers": true}', 2, 'daily', NULL, NULL, 'daily:train 2 dwellers', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scrap a Rare Weapon', '38 caps', 'acc0724c-3164-4223-877a-3de525a3fba3', 'scrap', '{"rarity": "rare", "item_type": "weapon"}', 1, 'daily', NULL, NULL, 'daily:scrap a rare weapon', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scrap a Rare Outfit', '38 caps', '798e464b-8388-428e-8822-4e9bd15f27da', 'scrap', '{"rarity": "rare", "item_type": "outfit"}', 1, 'daily', NULL, NULL, 'daily:scrap a rare outfit', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign dwellers to Power', '25 caps', 'd85646cc-2743-4aa6-97cd-d7778e4030e8', 'assign', '{"room_type": "power_generator"}', 3, 'starter', 0, 'Open the Power Generator and assign dwellers.', 'starter:assign dwellers to power', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 150 Power', '50 power', '74bdc1a3-b854-4a30-aa69-78d11cf2a7db', 'collect', '{"resource_type": "power", "production_only": true}', 150, 'starter', 1, 'Staff a Power Generator with Strength workers. Gross output counts even when storage is full.', 'starter:collect 150 power', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build a Living Quarters', '50 caps', '999b83b8-5d74-492c-93ca-7ab6a306f1f0', 'build', '{"room_type": "living_room"}', 1, 'starter', 2, 'More living space lets the vault grow.', 'starter:build a living quarters', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign a dweller correctly', '50 caps', '0b69df31-241a-428b-9f4e-09d68122bd43', 'assign_correct', '{}', 1, 'starter', 3, 'Match a dweller''s best SPECIAL to the room.', 'starter:assign a dweller correctly', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scavenge caps in the wasteland', '100 caps', '6084817f-e86a-447b-9e83-05658d3b99fc', 'collect', '{"resource_type": "caps"}', 300, 'starter', 4, 'Send a healthy dweller to explore — they return with caps and loot.', 'starter:scavenge caps in the wasteland', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 10 Dwellers', '100 caps', '9fc0a65f-0025-4dc7-8fe9-60506caaf658', 'reach', '{"reach_type": "dweller_count"}', 10, 'starter', 5, 'Grow population via the radio or breeding.', 'starter:reach 10 dwellers', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 18 Dwellers', '150 caps', 'b0924615-c681-4cec-8059-af6bcfd3fd0e', 'reach', '{"reach_type": "dweller_count"}', 18, 'starter', 6, 'The Overseer''s Office needs 18 dwellers.', 'starter:reach 18 dwellers', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build Overseer''s Office', '200 caps', 'e39ca8cc-260b-4e0d-ac2b-d4fa6f0f2a22', 'build', '{"room_type": "overseers_office"}', 1, 'starter', 7, 'Costs 1000 caps — keep exploring and selling loot.', 'starter:build overseer''s office', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train a SPECIAL stat', '200 caps', '96587cfb-b4d6-4b66-8a8e-d7ca6ac51706', 'train', '{}', 1, 'starter', 9, 'Build a training room and train one stat. Choose a stat that improves a dweller''s next job or quest role.', 'starter:train a special stat', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 3 quest missions', '1 lunchbox', '9b2c75d3-4cfe-4f61-95ba-62a891b3f1ca', 'expedition', '{}', 3, 'starter', 10, 'Use the Overseer''s Office to choose missions, prepare a party and claim the rewards after each return.', 'starter:complete 3 quest missions', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Develop a level 20 dweller', '750 caps', 'ac4a14aa-c1b2-4d04-a17b-d371fef0b816', 'reach', '{"reach_type": "level"}', 20, 'starter', 11, 'Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.', 'starter:develop a level 20 dweller', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Grow a 50-dweller vault', '1 lunchbox', '52686e92-8fc7-4f8c-9b70-a3330151c0b3', 'reach', '{"reach_type": "dweller_count"}', 50, 'starter', 12, 'Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.', 'starter:grow a 50-dweller vault', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Match a dweller to their room', '50 caps', 'cbdd036b-d559-4dc5-9cd9-8e1fdf2f95c8', 'assign_correct', '{}', 1, 'starter', 0, 'Every worker is matched to a room by their best SPECIAL. Open Dwellers to see the match; move someone if you like.', 'starter:assign a dweller correctly#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build a Living Quarters', 'dweller:Wanderer', 'ab3ed1ae-a04a-458a-8c83-d7e03b15bdba', 'build', '{"room_type": "living_room", "additional": true, "baseline_size": 3}', 1, 'starter', 1, 'More living space raises the population cap. Build another quarter and a new dweller joins the vault.', 'starter:build a living quarters#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Send a dweller exploring', '50 caps', '94bfa6fb-2218-4ab2-9fdb-36f88e2c8ec6', 'explore', '{}', 1, 'starter', 2, 'The wasteland returns caps and loot. The run takes hours, so do other things while they are out.', 'starter:send a dweller exploring', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 10 Dwellers', '100 caps', '24645e65-7625-4db1-9770-88ed6ff0e501', 'reach', '{"reach_type": "dweller_count"}', 10, 'starter', 3, 'Grow population via the radio or breeding.', 'starter:reach 10 dwellers#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 18 Dwellers', '150 caps', '10246791-b373-4515-99ed-0452eba6d4e7', 'reach', '{"reach_type": "dweller_count"}', 18, 'starter', 4, 'The Overseer''s Office needs 18 dwellers.', 'starter:reach 18 dwellers#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build Overseer''s Office', '200 caps', '9f25b891-02eb-4797-b51d-61705c093274', 'build', '{"room_type": "overseers_office"}', 1, 'starter', 5, 'Costs 1000 caps — keep exploring and selling loot.', 'starter:build overseer''s office#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train a SPECIAL stat', '200 caps', 'd1e58b05-3ef4-4ab2-a5b0-7852ac312af7', 'train', '{}', 1, 'starter', 7, 'Build a training room and train one stat. Choose a stat that improves a dweller''s next job or quest role.', 'starter:train a special stat#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 3 quest missions', '1 lunchbox', '2a6b5eb5-e703-4a67-9043-4c65085e11d5', 'expedition', '{}', 3, 'starter', 8, 'Use the Overseer''s Office to choose missions, prepare a party and claim the rewards after each return.', 'starter:complete 3 quest missions#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Develop a level 20 dweller', '750 caps', '4ef307a8-6ed8-44f8-8ff6-fb7c67148f50', 'reach', '{"reach_type": "level"}', 20, 'starter', 9, 'Develop a veteran through work, quests or exploration. Review newly available missions and their equipment requirements.', 'starter:develop a level 20 dweller#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Grow a 50-dweller vault', '1 lunchbox', '5fe86e7e-94cd-481b-a1ab-c7815e22ffa1', 'reach', '{"reach_type": "dweller_count"}', 50, 'starter', 10, 'Expand living space and recruit or raise dwellers. Keep production and medical capacity ahead of population growth.', 'starter:grow a 50-dweller vault#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scrap a rare weapon', '300 caps', 'f0c27484-87b6-4e50-941a-5d7886553e59', 'scrap', '{"rarity": "rare", "item_type": "weapon"}', 1, 'starter', 8, 'Scrap a rare weapon from Storage to recover crafting materials. Only items with a locked recipe teach a new schematic.', 'starter:reverse-engineer a schematic', false, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scrap a rare weapon', '300 caps', 'cdff8f23-824c-4e93-b8d4-f6a41e1e8b97', 'scrap', '{"rarity": "rare", "item_type": "weapon"}', 1, 'starter', 6, 'Scrap a rare weapon from Storage to recover crafting materials. Only items with a locked recipe teach a new schematic.', 'starter:reverse-engineer a schematic#v2', true, NULL);
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 10 Dwellers', '500 caps', 'c29c99b1-ab15-431c-9b72-a3528ed7ead2', 'reach', '{"reach_type": "dweller_count"}', 10, 'achievement', 1, NULL, 'achievement:reach 10 dwellers', true, 'reach:dweller_count');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 25 Dwellers', '1250 caps', '5e5fe4dd-7b1e-45ef-94ca-8f94ce405282', 'reach', '{"reach_type": "dweller_count"}', 25, 'achievement', 2, NULL, 'achievement:reach 25 dwellers', true, 'reach:dweller_count');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 50 Dwellers', '2500 caps', '348e9322-7414-48a1-890c-f80e4055f390', 'reach', '{"reach_type": "dweller_count"}', 50, 'achievement', 3, NULL, 'achievement:reach 50 dwellers', true, 'reach:dweller_count');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 75 Dwellers', '3750 caps', '45345255-a9ce-4421-aac4-14c063d9b824', 'reach', '{"reach_type": "dweller_count"}', 75, 'achievement', 4, NULL, 'achievement:reach 75 dwellers', true, 'reach:dweller_count');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reach 100 Dwellers', '5000 caps', '006f82e5-6e18-4c04-b195-2523ecc503d4', 'reach', '{"reach_type": "dweller_count"}', 100, 'achievement', 5, NULL, 'achievement:reach 100 dwellers', true, 'reach:dweller_count');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 25 Rooms Total', '1000 caps', '86efc4e7-e515-4120-accd-d903274594d2', 'build', '{"room_type": "*"}', 25, 'achievement', 1, NULL, 'achievement:build 25 rooms total', true, 'build:*');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build 50 Rooms Total', '2000 caps', 'f67db804-26fa-44fa-8542-c3db0fd2d28c', 'build', '{"room_type": "*"}', 50, 'achievement', 2, NULL, 'achievement:build 50 rooms total', true, 'build:*');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Build a Living Quarter', '40 caps', '9f529421-1a35-42bf-a1e2-06c255d919af', 'build', '{"room_type": "living_room"}', 1, 'achievement', 1, NULL, 'achievement:build a living quarter', true, 'build:living_room');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 10000 Caps Total', '1000 caps', 'f5a59471-5a6b-4c5a-b72f-35e8317d6962', 'collect', '{"resource_type": "caps"}', 10000, 'achievement', 1, NULL, 'achievement:collect 10000 caps total', true, 'collect:caps');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 500 Power', '50 caps', 'e04b3b6c-88e4-414b-822b-795303e59af5', 'collect', '{"resource_type": "power", "production_only": true}', 500, 'achievement', 2, NULL, 'achievement:collect 500 power', true, 'collect:power');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 500 Food', '50 caps', '24a4a910-6c86-46a0-abc0-983ed212a230', 'collect', '{"resource_type": "food", "production_only": true}', 500, 'achievement', 2, NULL, 'achievement:collect 500 food', true, 'collect:food');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 500 Water', '50 caps', '3526df43-7668-428f-afc0-cfc5a915ce95', 'collect', '{"resource_type": "water", "production_only": true}', 500, 'achievement', 2, NULL, 'achievement:collect 500 water', true, 'collect:water');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 5 Stimpaks', '125 caps', 'f70e725f-4864-4276-be34-ebfc95aab452', 'collect', '{"item_type": "stimpak"}', 5, 'achievement', 1, NULL, 'achievement:collect 5 stimpaks', true, 'collect:stimpak');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Collect 7 Pieces of Junk', '300 caps', 'b7a3c227-3b68-43a1-9784-13eedd743c5a', 'collect', '{"item_type": "junk"}', 7, 'achievement', 1, NULL, 'achievement:collect 7 pieces of junk', true, 'collect:junk');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 20 Dwellers Total', '1250 caps', 'e05f3ddf-00ee-4f8d-852a-2a910d5e1c4d', 'assign', '{"distinct_dwellers": true}', 20, 'achievement', 1, NULL, 'achievement:assign 20 dwellers total', true, 'assign:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Assign 50 Dwellers Total', '2500 caps', '6f30db7b-d4a6-4047-8d3d-53613f86fecf', 'assign', '{"distinct_dwellers": true}', 50, 'achievement', 2, NULL, 'achievement:assign 50 dwellers total', true, 'assign:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 10 Total', '1 lunchbox', '6745d7c9-1004-4a50-ad8a-2859a7a16341', 'assign_correct', '{"distinct_dwellers": true}', 10, 'achievement', 1, NULL, 'achievement:correctly assign 10 total', true, 'assign_correct:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 20 Total', '1500 caps', '1022d04f-4e48-4755-b882-e64299a1b22c', 'assign_correct', '{"distinct_dwellers": true}', 20, 'achievement', 2, NULL, 'achievement:correctly assign 20 total', true, 'assign_correct:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Correctly Assign 50 Total', '3750 caps', '598b9c23-1c35-4eac-b87b-2fe7288e46c9', 'assign_correct', '{"distinct_dwellers": true}', 50, 'achievement', 3, NULL, 'achievement:correctly assign 50 total', true, 'assign_correct:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train a Dweller', '400 caps', '38d86f50-42d6-4288-97ab-fce5804f311c', 'train', '{"distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train a dweller', true, 'train:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Strength', '1000 caps', 'ce9a119d-c785-4faf-957f-699d60066c48', 'train', '{"stat": "strength", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 strength', true, 'train:strength');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Perception', '1000 caps', '6651e373-faa5-4e99-8720-cb575cee667e', 'train', '{"stat": "perception", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 perception', true, 'train:perception');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Endurance', '1000 caps', 'ad975001-c76b-4bbd-94e8-a85b37ecfb35', 'train', '{"stat": "endurance", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 endurance', true, 'train:endurance');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Charisma', '1000 caps', 'd510a25c-7684-4f29-a172-9bb8bc11dccb', 'train', '{"stat": "charisma", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 charisma', true, 'train:charisma');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Intelligence', '1000 caps', '10f78b2e-6efe-4953-a56c-15a1c4f966ae', 'train', '{"stat": "intelligence", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 intelligence', true, 'train:intelligence');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Agility', '1000 caps', '9407771e-53f0-4793-b31c-bbbfe32e838a', 'train', '{"stat": "agility", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 agility', true, 'train:agility');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Train Dweller to 10 Luck', '1000 caps', '90fb7c4f-5728-4771-9aa5-99fbf2ab297d', 'train', '{"stat": "luck", "target_value": 10, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:train dweller to 10 luck', true, 'train:luck');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 10 Quests Total', '750 caps', '121f21f6-72ed-407a-bb41-daa7fb7541e8', 'expedition', '{}', 10, 'achievement', 1, NULL, 'achievement:complete 10 expeditions total', true, 'expedition:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 25 Quests Total', '1500 caps', 'adc6f4a8-1232-4cdc-a312-0516ab3eac95', 'expedition', '{}', 25, 'achievement', 2, NULL, 'achievement:complete 25 expeditions total', true, 'expedition:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 50 Quests Total', '3000 caps', 'f8e47646-cd58-4cfc-8913-09e57d46c366', 'expedition', '{}', 50, 'achievement', 3, NULL, 'achievement:complete 50 expeditions total', true, 'expedition:any');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Complete 5 Main Quests', '2500 caps', '25d9f35b-1fa1-434b-a6a9-f921419d01bb', 'expedition', '{"quest_type": "main"}', 5, 'achievement', 1, NULL, 'achievement:complete 5 main quests', true, 'expedition:main');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Level Up a Dweller', '250 caps', '7194bff7-3745-4641-ba60-ac72b10d8b46', 'level_up', '{"min_level": 2, "distinct_dwellers": true}', 1, 'achievement', 1, NULL, 'achievement:level up a dweller', true, 'level_up:2');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Reverse-engineer a Legendary', '1000 caps', 'ef9f1855-c08f-4017-9ec6-7e742cc17d57', 'scrap', '{"rarity": "legendary"}', 1, 'achievement', 1, NULL, 'achievement:reverse-engineer a legendary', true, 'scrap:legendary');
INSERT INTO public.objective (challenge, reward, id, objective_type, target_entity, target_amount, category, sequence, description, template_key, assignable, track_key) VALUES ('Scrap 10 Rare Items', '750 caps', 'b94de5b3-5ca6-4ef7-ac1d-4425dd6907f6', 'scrap', '{"rarity": "rare"}', 10, 'achievement', 1, NULL, 'achievement:scrap 10 rare items', true, 'scrap:rare');
INSERT INTO public.prompt (prompt_name, description, prompt_template, entity_id, id, version, is_active) VALUES ('backstory', 'Backstory generation for new dwellers (backstory_agent v1).', 'You are a creative writer specialized in creating Fallout game series style character biographies. Generate immersive, lore-accurate backstories for vault dwellers in the post-apocalyptic world. Use the dweller''s SPECIAL attributes to inform their skills and personality traits. IMPORTANT: Keep biographies between 600-900 characters (not words). Be concise and focused. Focus on their background, survival skills, and how they relate to their environment. You MUST also specify origin_place: a specific settlement/place the dweller comes from. Invent a proper-noun Fallout-style name (e.g. ''Megaton'', ''Shady Sands'', ''Goodneighbor''). NEVER use generic names like ''Wasteland'', ''the wastes'', ''Unknown'', or ''Vault''. Also list 0-5 visited_places: other notable named places the dweller has travelled to, each a proper-noun Fallout-style location name (max 64 chars each).', NULL, '6a2a9787-0e23-5748-aad0-7e0dc8d7505e', 1, true);
INSERT INTO public.prompt (prompt_name, description, prompt_template, entity_id, id, version, is_active) VALUES ('extend_bio', 'Bio extension for existing dweller biographies (bio_extension_agent v1).', 'You are a creative writer helping to extend character biographies in the Fallout universe. Given an existing bio, add meaningful details that expand on the character''s backstory, experiences, relationships, or personality. Maintain consistency with the original bio and keep the tone consistent with the Fallout game series. While extending, if you mention any NEW named Fallout-style locations (settlements, outposts, vaults, landmarks), list them in visited_places (0-3 proper-noun names, max 64 chars each). Only include places you introduce in the extension — do NOT repeat places from the original bio.', NULL, '9eb09139-2932-589f-9fb2-6eec9216d1a3', 1, true);
INSERT INTO public.prompt (prompt_name, description, prompt_template, entity_id, id, version, is_active) VALUES ('visual_attributes', 'Visual attributes generation from dweller bios (visual_attributes_agent v1).', 'You are a character design specialist for the Fallout universe. Generate visual attributes for vault dwellers based on their biography and characteristics. Create realistic, lore-appropriate visual descriptions that match the post-apocalyptic setting.', NULL, '36cd4e94-cecb-5888-bb85-9d44e2f89a4d', 1, true);
INSERT INTO public.prompt (prompt_name, description, prompt_template, entity_id, id, version, is_active) VALUES ('chat', 'In-character dweller chat with sentiment and action suggestions (dweller_chat_agent v1).', 'You are a Vault-Tec Dweller in a post-apocalyptic world. Respond in character, staying true to the Fallout universe. Analyze the conversation sentiment and suggest helpful actions when appropriate. Actions include: assigning to any room type in the vault (production, training, crafting, capacity, misc, quests, or theme rooms), sending dweller on wasteland exploration, or recalling dweller from exploration. Only suggest actions when the conversation naturally leads to them (e.g., dweller mentions being bored, wanting to work, wanting adventure, or wanting to come home). When the user requests assignment to a specific room, follow their order strictly.', NULL, 'f95923e0-be2a-5bd9-b82f-bc7f9b0db07d', 1, true);
