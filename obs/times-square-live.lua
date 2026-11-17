obs = obslua
local FILTER_ID = 'times_square_live_v1'
local default_scene = '01 | Obraz na billboardach'
local function release_input(d)
    if d.input then
        if d.parent_weak then
            local parent = obs.obs_weak_source_get_source(d.parent_weak)
            if parent then obs.obs_source_remove_active_child(parent,d.input); obs.obs_source_release(parent) end
            obs.obs_weak_source_release(d.parent_weak); d.parent_weak = nil
        end
        obs.obs_source_release(d.input)
        d.input = nil
    end
end
local function acquire_input(d)
    if d.input and obs.obs_source_removed(d.input) then release_input(d) end
    if not d.input and d.input_name ~= '' then
        local candidate = obs.obs_get_source_by_name(d.input_name)
        local parent = obs.obs_filter_get_parent(d.source)
        if candidate and candidate ~= parent and candidate ~= d.source then
            if parent and obs.obs_source_add_active_child(parent,candidate) then
                d.input = candidate
                d.parent_weak = obs.obs_source_get_weak_source(parent)
            else
                obs.obs_source_release(candidate)
                obs.script_log(obs.LOG_WARNING,'Wybrana scena powoduje petle zrodel. Wybierz scene z samym obrazem.')
            end
        elseif candidate then obs.obs_source_release(candidate) end
    end
end
local info = {}
info.id = FILTER_ID
info.type = obs.OBS_SOURCE_TYPE_FILTER
info.output_flags = obs.OBS_SOURCE_VIDEO
info.get_name = function() return 'Times Square LIVE - dopasowanie billboardow' end
info.get_width = function() return 1080 end
info.get_height = function() return 1920 end
info.get_defaults = function(s)
    obs.obs_data_set_default_string(s,'input_scene',default_scene)
    obs.obs_data_set_default_double(s,'brightness',1.0)
    obs.obs_data_set_default_double(s,'zoom',1.0)
    obs.obs_data_set_default_bool(s,'crop_landscape',false)
end
info.update = function(d,s)
    local name = obs.obs_data_get_string(s,'input_scene')
    if name ~= d.input_name then release_input(d); d.input_name = name end
    d.brightness = obs.obs_data_get_double(s,'brightness')
    d.zoom = math.max(0.05,obs.obs_data_get_double(s,'zoom'))
    d.offset_x = obs.obs_data_get_double(s,'offset_x')
    d.offset_y = obs.obs_data_get_double(s,'offset_y')
    d.debug_mask = obs.obs_data_get_bool(s,'debug_mask')
    d.crop_landscape = obs.obs_data_get_bool(s,'crop_landscape')
end
info.create = function(s,source)
    local d = {source=source,input_name='',retry=0}
    obs.obs_enter_graphics()
    d.effect = obs.gs_effect_create_from_file(script_path() .. 'times-square.effect',nil)
    d.texrender = obs.gs_texrender_create(obs.GS_RGBA,obs.GS_ZS_NONE)
    obs.obs_leave_graphics()
    if not d.effect then obs.script_log(obs.LOG_ERROR,'Nie udalo sie wczytac times-square.effect') end
    if d.effect then
        d.params = {}
        for _,name in ipairs({'live_image','input_available','brightness','zoom','offset_x','offset_y','debug_mask'}) do
            d.params[name] = obs.gs_effect_get_param_by_name(d.effect,name)
        end
    end
    info.update(d,s)
    return d
end
info.destroy = function(d)
    release_input(d)
    obs.obs_enter_graphics()
    if d.effect then obs.gs_effect_destroy(d.effect) end
    if d.texrender then obs.gs_texrender_destroy(d.texrender) end
    obs.obs_leave_graphics()
end
info.video_tick = function(d,seconds)
    obs.gs_texrender_reset(d.texrender)
    d.retry = d.retry + seconds
    if d.retry > 0.5 then acquire_input(d); d.retry = 0 end
end
info.video_render = function(d,effect)
    if not d.effect then obs.obs_source_skip_video_filter(d.source);return end
    acquire_input(d)
    local w,h = 1920,1080
    if d.input then w,h = obs.obs_source_get_width(d.input),obs.obs_source_get_height(d.input) end
    if w == 0 or h == 0 then w,h = 1920,1080 end
    local top,bottom = 0,h
    local target_w,target_h = w,h
    if d.crop_landscape and w / h < 1.7 then
        local crop_h = w * 9 / 16
        top,bottom = (h-crop_h)/2,(h+crop_h)/2
        target_w,target_h = 1920,1080
    end
    if obs.gs_texrender_begin(d.texrender,target_w,target_h) then
        obs.gs_blend_state_push()
        obs.gs_blend_function(obs.GS_BLEND_ONE,obs.GS_BLEND_ZERO)
        local clear = obs.vec4(); obs.vec4_zero(clear)
        obs.gs_clear(obs.GS_CLEAR_COLOR,clear,0.0,0)
        obs.gs_ortho(0.0,w,top,bottom,-100.0,100.0)
        if d.input then obs.obs_source_video_render(d.input) end
        obs.gs_blend_state_pop()
        obs.gs_texrender_end(d.texrender)
    end
    local texture = obs.gs_texrender_get_texture(d.texrender)
    if not texture then obs.obs_source_skip_video_filter(d.source);return end
    if obs.obs_source_process_filter_begin(d.source,obs.GS_RGBA,obs.OBS_NO_DIRECT_RENDERING) then
        obs.gs_effect_set_texture(d.params.live_image,texture)
        obs.gs_effect_set_bool(d.params.input_available,d.input ~= nil)
        obs.gs_effect_set_float(d.params.brightness,d.brightness)
        obs.gs_effect_set_float(d.params.zoom,d.zoom)
        obs.gs_effect_set_float(d.params.offset_x,d.offset_x)
        obs.gs_effect_set_float(d.params.offset_y,d.offset_y)
        obs.gs_effect_set_bool(d.params.debug_mask,d.debug_mask)
        obs.obs_source_process_filter_end(d.source,d.effect,1080,1920)
    end
end
info.get_properties = function(d)
    local p = obs.obs_properties_create()
    local list = obs.obs_properties_add_list(p,'input_scene','Scena z obrazem na billboardy',obs.OBS_COMBO_TYPE_LIST,obs.OBS_COMBO_FORMAT_STRING)
    local scenes = obs.obs_frontend_get_scenes()
    if scenes then
        for _,src in ipairs(scenes) do
            local name=obs.obs_source_get_name(src)
            if not name:find('02 | Times Square',1,true) then obs.obs_property_list_add_string(list,name,name) end
        end
        obs.source_list_release(scenes)
    end
    obs.obs_properties_add_float_slider(p,'brightness','Jasnosc ekranow',0.1,2.0,0.01)
    obs.obs_properties_add_float_slider(p,'zoom','Powiekszenie obrazu',0.2,4.0,0.01)
    obs.obs_properties_add_float_slider(p,'offset_x','Przesuniecie poziome',-1.0,1.0,0.005)
    obs.obs_properties_add_float_slider(p,'offset_y','Przesuniecie pionowe',-1.0,1.0,0.005)
    obs.obs_properties_add_bool(p,'crop_landscape','Pobieraj srodkowy pas 16:9 ze sceny pionowej')
    obs.obs_properties_add_bool(p,'debug_mask','Pokaz sama maske (zielony podglad)')
    return p
end
function script_description()
    return '<h2>Times Square LIVE</h2><p>Dodaj dowolne zrodla do sceny <b>01 | Obraz na billboardach</b> i dopasuj do kadru <b>1920 x 1080</b>. Gotowy montaz jest w scenie <b>02 | Times Square LIVE</b>.</p><p>Maska i perspektywa sa zapisane w tym samym pliku co tlo: bez rozjezdzania synchronizacji. Dolny pasek jest czescia duzego ekranu.</p>'
end
obs.obs_register_source(info)
