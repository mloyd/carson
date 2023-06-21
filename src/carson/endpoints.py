MAP_ATTR_TO_ENDPOINT = {
    'STATUS': {
        'TYPE': 'GET',
        'URI': 'status',
        'AUTH': False
    },
    'AUTHENTICATE': {
        'TYPE': 'POST',
        'URI': 'oauth/token',
        'AUTH': False
    },
    'REVOKE_AUTH_TOKEN': {
        'TYPE': 'POST',
        'URI': 'oauth/revoke',
        'AUTH': True
    },
    'PRODUCT_LIST': {
        'TYPE': 'GET',
        'URI': 'api/1/products',
        'AUTH': True
    },
    'VEHICLE_LIST': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles',
        'AUTH': True
    },
    'VEHICLE_SUMMARY': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}',
        'AUTH': True
    },
    'VEHICLE_DATA_LEGACY': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/data',
        'AUTH': True
    },
    'VEHICLE_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/vehicle_data',
        'AUTH': True
    },
    'VEHICLE_SERVICE_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/service_data',
        'AUTH': True
    },
    'NEARBY_CHARGING_SITES': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/nearby_charging_sites',
        'AUTH': True
    },
    'WAKE_UP': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/wake_up',
        'AUTH': True
    },
    'UNLOCK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/door_unlock',
        'AUTH': True
    },
    'LOCK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/door_lock',
        'AUTH': True
    },
    'HONK_HORN': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/honk_horn',
        'AUTH': True
    },
    'FLASH_LIGHTS': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/flash_lights',
        'AUTH': True
    },
    'CLIMATE_ON': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/auto_conditioning_start',
        'AUTH': True
    },
    'CLIMATE_OFF': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/auto_conditioning_stop',
        'AUTH': True
    },
    'MAX_DEFROST': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/set_preconditioning_max',
        'AUTH': True
    },
    'CHANGE_CLIMATE_TEMPERATURE_SETTING': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/set_temps',
        'AUTH': True
    },
    'CHANGE_CHARGE_LIMIT': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/set_charge_limit',
        'AUTH': True
    },
    'CHANGE_SUNROOF_STATE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/sun_roof_control',
        'AUTH': True
    },
    'WINDOW_CONTROL': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/window_control',
        'AUTH': True
    },
    'ACTUATE_TRUNK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/actuate_trunk',
        'AUTH': True
    },
    'REMOTE_START': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/remote_start_drive',
        'AUTH': True
    },
    'TRIGGER_HOMELINK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/trigger_homelink',
        'AUTH': True
    },
    'CHARGE_PORT_DOOR_OPEN': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/charge_port_door_open',
        'AUTH': True
    },
    'CHARGE_PORT_DOOR_CLOSE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/charge_port_door_close',
        'AUTH': True
    },
    'START_CHARGE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/charge_start',
        'AUTH': True
    },
    'STOP_CHARGE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/charge_stop',
        'AUTH': True
    },
    'MEDIA_TOGGLE_PLAYBACK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_toggle_playback',
        'AUTH': True
    },
    'MEDIA_NEXT_TRACK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_next_track',
        'AUTH': True
    },
    'MEDIA_PREVIOUS_TRACK': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_prev_track',
        'AUTH': True
    },
    'MEDIA_NEXT_FAVORITE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_next_fav',
        'AUTH': True
    },
    'MEDIA_PREVIOUS_FAVORITE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_prev_fav',
        'AUTH': True
    },
    'MEDIA_VOLUME_UP': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_volume_up',
        'AUTH': True
    },
    'MEDIA_VOLUME_DOWN': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/media_volume_down',
        'AUTH': True
    },
    'SEND_LOG': {
        'TYPE': 'POST',
        'URI': 'api/1/logs',
        'AUTH': True
    },
    'SEND_REPORT': {
        'TYPE': 'POST',
        'URI': 'api/1/reports',
        'AUTH': True
    },
    'RETRIEVE_NOTIFICATION_PREFERENCES': {
        'TYPE': 'GET',
        'URI': 'api/1/notification_preferences',
        'AUTH': True
    },
    'SEND_NOTIFICATION_PREFERENCES': {
        'TYPE': 'POST',
        'URI': 'api/1/notification_preferences',
        'AUTH': True
    },
    'RETRIEVE_NOTIFICATION_SUBSCRIPTION_PREFERENCES': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicle_subscriptions',
        'AUTH': True
    },
    'SEND_NOTIFICATION_SUBSCRIPTION_PREFERENCES': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicle_subscriptions',
        'AUTH': True
    },
    'DEACTIVATE_DEVICE_TOKEN': {
        'TYPE': 'POST',
        'URI': 'api/1/device/{device_token}/deactivate',
        'AUTH': True
    },
    'CALENDAR_SYNC': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/upcoming_calendar_entries',
        'AUTH': True
    },
    'SET_VALET_MODE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/set_valet_mode',
        'AUTH': True
    },
    'RESET_VALET_PIN': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/reset_valet_pin',
        'AUTH': True
    },
    'SPEED_LIMIT_ACTIVATE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/speed_limit_activate',
        'AUTH': True
    },
    'SPEED_LIMIT_DEACTIVATE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/speed_limit_deactivate',
        'AUTH': True
    },
    'SPEED_LIMIT_SET_LIMIT': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/speed_limit_set_limit',
        'AUTH': True
    },
    'SPEED_LIMIT_CLEAR_PIN': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/speed_limit_clear_pin',
        'AUTH': True
    },
    'SCHEDULE_SOFTWARE_UPDATE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/schedule_software_update',
        'AUTH': True
    },
    'CANCEL_SOFTWARE_UPDATE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/cancel_software_update',
        'AUTH': True
    },
    'SET_SENTRY_MODE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/set_sentry_mode',
        'AUTH': True
    },
    'POWERWALL_ORDER_SESSION_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/users/powerwall_order_entry_data',
        'AUTH': True
    },
    'POWERWALL_ORDER_PAGE': {
        'TYPE': 'GET',
        'URI': 'powerwall_order_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'ONBOARDING_EXPERIENCE': {
        'TYPE': 'GET',
        'URI': 'api/1/users/onboarding_data',
        'AUTH': True
    },
    'ONBOARDING_EXPERIENCE_PAGE': {
        'TYPE': 'GET',
        'URI': 'onboarding_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'SERVICE_SELF_SCHEDULING_ELIGIBILITY': {
        'TYPE': 'GET',
        'URI': 'api/1/users/service_scheduling_data',
        'AUTH': True
    },
    'SERVICE_SELF_SCHEDULING_PAGE': {
        'TYPE': 'GET',
        'URI': 'service_scheduling_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'REFERRAL_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/users/referral_data',
        'AUTH': True
    },
    'REFERRAL_PAGE': {
        'TYPE': 'GET',
        'URI': 'referral_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'ROADSIDE_ASSISTANCE_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/users/roadside_assistance_data',
        'AUTH': True
    },
    'ROADSIDE_ASSISTANCE_PAGE': {
        'TYPE': 'GET',
        'URI': 'roadside_assistance_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'UPGRADE_ELIGIBILITY': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/eligible_upgrades',
        'AUTH': True
    },
    'UPGRADE_URL': {
        'TYPE': 'GET',
        'URI': 'api/1/vehicles/{vehicle_id}/purchase_url',
        'AUTH': True
    },
    'MESSAGE_CENTER_MESSAGE_LIST': {
        'TYPE': 'GET',
        'URI': 'api/1/messages',
        'AUTH': True
    },
    'MESSAGE_CENTER_MESSAGE': {
        'TYPE': 'GET',
        'URI': 'api/1/messages/{message_id}',
        'AUTH': True
    },
    'MESSAGE_CENTER_COUNTS': {
        'TYPE': 'GET',
        'URI': 'api/1/messages/count',
        'AUTH': True
    },
    'MESSAGE_CENTER_MESSAGE_ACTION_UPDATE': {
        'TYPE': 'POST',
        'URI': 'api/1/messages/{message_id}/actions',
        'AUTH': True
    },
    'MESSAGE_CENTER_CTA_PAGE': {
        'TYPE': 'GET',
        'URI': 'messages_cta_page',
        'AUTH': True,
        'CONTENT': 'HTML'
    },
    'AUTH_COMMAND_TOKEN': {
        'TYPE': 'POST',
        'URI': 'api/1/users/command_token',
        'AUTH': True
    },
    'SEND_DEVICE_KEY': {
        'TYPE': 'POST',
        'URI': 'api/1/users/keys',
        'AUTH': True
    },
    'DIAGNOSTICS_ENTITLEMENTS': {
        'TYPE': 'GET',
        'URI': 'api/1/diagnostics',
        'AUTH': True
    },
    'SEND_DIAGNOSTICS': {
        'TYPE': 'POST',
        'URI': 'api/1/diagnostics',
        'AUTH': True
    },
    'BATTERY_SUMMARY': {
        'TYPE': 'GET',
        'URI': 'api/1/powerwalls/{battery_id}/status',
        'AUTH': True
    },
    'BATTERY_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/powerwalls/{battery_id}',
        'AUTH': True
    },
    'BATTERY_POWER_TIMESERIES_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/powerwalls/{battery_id}/powerhistory',
        'AUTH': True
    },
    'BATTERY_ENERGY_TIMESERIES_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/powerwalls/{battery_id}/energyhistory',
        'AUTH': True
    },
    'BATTERY_BACKUP_RESERVE': {
        'TYPE': 'POST',
        'URI': 'api/1/powerwalls/{battery_id}/backup',
        'AUTH': True
    },
    'BATTERY_SITE_NAME': {
        'TYPE': 'POST',
        'URI': 'api/1/powerwalls/{battery_id}/site_name',
        'AUTH': True
    },
    'BATTERY_OPERATION_MODE': {
        'TYPE': 'POST',
        'URI': 'api/1/powerwalls/{battery_id}/operation',
        'AUTH': True
    },
    'SITE_SUMMARY': {
        'TYPE': 'GET',
        'URI': 'api/1/energy_sites/{site_id}/status',
        'AUTH': True
    },
    'SITE_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/energy_sites/{site_id}/live_status',
        'AUTH': True
    },
    'SITE_CONFIG': {
        'TYPE': 'GET',
        'URI': 'api/1/energy_sites/{site_id}/site_info',
        'AUTH': True
    },
    'HISTORY_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/energy_sites/{site_id}/history',
        'AUTH': True
    },
    'CALENDAR_HISTORY_DATA': {
        'TYPE': 'GET',
        'URI': 'api/1/energy_sites/{site_id}/calendar_history',
        'AUTH': True
    },
    'BACKUP_RESERVE': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/backup',
        'AUTH': True
    },
    'OFF_GRID_VEHICLE_CHARGING_RESERVE': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/off_grid_vehicle_charging_reserve',
        'AUTH': True
    },
    'SITE_NAME': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/site_name',
        'AUTH': True
    },
    'OPERATION_MODE': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/operation',
        'AUTH': True
    },
    'TIME_OF_USE_SETTINGS': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/time_of_use_settings',
        'AUTH': True
    },
    'STORM_MODE_SETTINGS': {
        'TYPE': 'POST',
        'URI': 'api/1/energy_sites/{site_id}/storm_mode',
        'AUTH': True
    },
    'SEND_NOTIFICATION_CONFIRMATION': {
        'TYPE': 'POST',
        'URI': 'api/1/notification_confirmations',
        'AUTH': True
    },
    'SHARE_TO_VEHICLE': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/share',
        'AUTH': True
    },
    'REMOTE_SEAT_HEATER_REQUEST': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/remote_seat_heater_request',
        'AUTH': True
    },
    'REMOTE_STEERING_WHEEL_HEATER_REQUEST': {
        'TYPE': 'POST',
        'URI': 'api/1/vehicles/{vehicle_id}/command/remote_steering_wheel_heater_request',
        'AUTH': True
    }
}
