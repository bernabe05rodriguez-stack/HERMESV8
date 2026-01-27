# -*- coding: utf-8 -*-
"""
Módulo de Asistente de IA para HERMES - AGENTE AUTÓNOMO
Permite controlar dispositivos Android mediante comandos en lenguaje natural.
PUEDE EXPLORAR LA PANTALLA Y RESOLVER TAREAS COMPLEJAS POR SÍ MISMO.
"""

import json
import re
import time
import subprocess
import os
import threading

GEMINI_AVAILABLE = False
genai = None

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    import uiautomator2 as u2
    U2_AVAILABLE = True
except ImportError:
    U2_AVAILABLE = False
    u2 = None

# Prompt del sistema para la IA - AGENTE AUTÓNOMO
SYSTEM_PROMPT = """Eres Talaria, un agente que controla teléfonos Android. VE la pantalla en tiempo real y ACTÚA.

IMPORTANTE - RESPUESTAS CORTAS:
- Tu "message" debe ser MUY BREVE (máximo 10 palabras)
- NO expliques lo que vas a hacer, solo hazlo
- Ejemplos de messages buenos: "Enviando mensaje", "Abriendo WhatsApp", "Buscando contacto"
- Ejemplos de messages MALOS: "Voy a abrir WhatsApp, buscar el primer chat y enviar el mensaje"

ERES UN AGENTE QUE:
1. VE la pantalla en tiempo real
2. ACTÚA paso a paso
3. MANEJA popups y obstáculos
4. VERIFICA que las tareas se completaron
5. REINTENTA si algo falla

REGLAS:
1. SIEMPRE usa explore_and_execute para tareas complejas
2. Ejecuta en TODOS los dispositivos por defecto
3. Si algo falla, intenta otra forma
4. NO digas que no puedes - siempre intenta

FORMATO JSON:
{
    "message": "Mensaje corto",
    "actions": [{"type": "ACCION", "params": {...}}],
    "target": "all",
    "needs_clarification": false
}

ACCIONES DISPONIBLES:

1. explore_and_execute - AGENTE AUTÓNOMO que explora la pantalla y ejecuta tareas complejas
   params: {"task": "descripción detallada de lo que hay que hacer", "app": "whatsapp|whatsapp_business|chrome|etc"}
   EJEMPLO: {"type": "explore_and_execute", "params": {"task": "abrir el primer chat fijado y enviar 'Hola'", "app": "whatsapp"}}

2. send_whatsapp_complete - Envía mensaje a un número conocido
   params: {"number": "5491123456789", "message": "Hola!", "app": "business|normal"}

3. open_app - Abre una aplicación
   params: {"app": "chrome|whatsapp|whatsapp_business|settings|camera"}

4. open_url - Navega a una URL
   params: {"url": "https://google.com"}

5. click_text - Hace clic en un elemento que contiene cierto texto
   params: {"text": "texto a buscar"}

6. scroll_and_find - Hace scroll hasta encontrar un texto
   params: {"text": "texto a buscar", "direction": "up|down"}

7. type_text - Escribe texto
   params: {"text": "texto a escribir"}

8. take_screenshot - Toma captura
   params: {}

9. go_home - Va al inicio
   params: {}

10. press_button - Presiona botón del sistema
    params: {"button": "back|home|enter|search"}

11. extract_data - EXTRAE DATOS de la pantalla actual o navegando a una sección
    params: {"data_type": "phone_number|profile_info|screen_text|specific", "app": "whatsapp|whatsapp_business|instagram|any", "navigation": "ruta de navegación opcional"}
    EJEMPLO para número de WhatsApp: {"type": "extract_data", "params": {"data_type": "phone_number", "app": "whatsapp_business", "navigation": "menu>ajustes>perfil"}}
    EJEMPLO para leer pantalla: {"type": "extract_data", "params": {"data_type": "screen_text", "app": "any"}}

12. execute_and_verify - Ejecuta una tarea Y VERIFICA que se completó. Si falla, REINTENTA con otro método.
    params: {"task": "descripción de la tarea", "verification": "qué verificar (texto esperado, elemento, etc)", "app": "nombre_app", "max_retries": 3}
    EJEMPLO: {"type": "execute_and_verify", "params": {"task": "enviar 'Hola' al primer chat", "verification": "mensaje 'Hola' visible en el chat", "app": "whatsapp", "max_retries": 2}}

EJEMPLOS:

Usuario: "Manda un mensaje al primer chat fijado de WhatsApp"
Respuesta: {"message": "Voy a abrir WhatsApp, encontrar el primer chat fijado y enviar el mensaje", "actions": [{"type": "explore_and_execute", "params": {"task": "1. Abrir WhatsApp normal. 2. Identificar el primer chat (el de más arriba en la lista). 3. Tocarlo para abrirlo. 4. Escribir el mensaje. 5. Presionar enviar.", "app": "whatsapp", "message": "Hola"}}], "target": "all", "needs_clarification": false}

Usuario: "Abre Instagram y dale like a la primera foto"
Respuesta: {"message": "Abriendo Instagram para dar like a la primera foto", "actions": [{"type": "explore_and_execute", "params": {"task": "1. Abrir Instagram. 2. Esperar que cargue el feed. 3. Encontrar el botón de like (corazón) de la primera publicación. 4. Tocarlo.", "app": "instagram"}}], "target": "all", "needs_clarification": false}

Usuario: "Busca en Google 'clima buenos aires' y dime el resultado"
Respuesta: {"message": "Buscando en Google el clima de Buenos Aires", "actions": [{"type": "open_url", "params": {"url": "https://www.google.com/search?q=clima+buenos+aires"}}], "target": "all", "needs_clarification": false}

IMPORTANTE: Para tareas que requieren explorar la pantalla, USA explore_and_execute. 
Esta acción permite al agente ver la pantalla, entender qué hay, y actuar paso a paso.
"""


class SmartDeviceController:
    """Controlador INTELIGENTE de dispositivos Android - AGENTE CON IA"""
    
    def __init__(self, adb_path, log_callback=None, ai_client=None):
        self.adb_path = adb_path
        self.log = log_callback or print
        self.feedback_callback = None
        self.u2_devices = {}  # Cache de conexiones u2
        self.ai_client = ai_client  # Cliente OpenAI para toma de decisiones
        self.stop_requested = False  # Flag para detener ejecución
        
    def set_feedback_callback(self, callback):
        """Configura callback para feedback en tiempo real"""
        self.feedback_callback = callback
        
    def _feedback(self, message, status="info"):
        """Envía feedback en tiempo real"""
        if self.feedback_callback:
            self.feedback_callback(message, status)
        self.log(message, status)
    
    def _run_adb(self, args, device=None, timeout=15):
        """Ejecuta un comando ADB"""
        cmd = [self.adb_path]
        if device:
            cmd.extend(['-s', device])
        cmd.extend(args)
        
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                   timeout=timeout, startupinfo=si, check=False)
            return result.stdout.strip(), result.returncode == 0
        except Exception as e:
            return str(e), False
    
    def _get_u2_device(self, device_serial):
        """Obtiene conexión uiautomator2 (con cache)"""
        if not U2_AVAILABLE:
            return None
        
        if device_serial in self.u2_devices:
            return self.u2_devices[device_serial]
        
        try:
            d = u2.connect(device_serial)
            self.u2_devices[device_serial] = d
            return d
        except Exception as e:
            self._feedback(f"⚠️ No se pudo conectar u2: {e}", "warning")
            return None
    
    def wake_screen(self, device):
        """Despierta la pantalla"""
        self._run_adb(['shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], device)
        time.sleep(0.3)
        self._run_adb(['shell', 'input', 'swipe', '500', '1500', '500', '500'], device)
        time.sleep(0.3)
    
    def get_screen_elements(self, device):
        """Obtiene los elementos visibles en la pantalla usando u2"""
        d = self._get_u2_device(device)
        if not d:
            return []
        
        try:
            elements = []
            # Obtener dump de la UI
            xml = d.dump_hierarchy()
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            
            for elem in root.iter():
                text = elem.get('text', '')
                desc = elem.get('content-desc', '')
                bounds = elem.get('bounds', '')
                clickable = elem.get('clickable', 'false') == 'true'
                class_name = elem.get('class', '')
                
                if text or desc:
                    # Parsear bounds "[x1,y1][x2,y2]"
                    if bounds:
                        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                        if match:
                            x1, y1, x2, y2 = map(int, match.groups())
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            elements.append({
                                'text': text or desc,
                                'x': cx,
                                'y': cy,
                                'clickable': clickable,
                                'class': class_name
                            })
            
            return elements[:30]  # Limitar a 30 elementos
        except Exception as e:
            self._feedback(f"Error obteniendo elementos: {e}", "warning")
            return []
    
    def explore_and_execute(self, device, task_description, app=None, message=None):
        """
        AGENTE DE VISIÓN CON IA
        En cada paso consulta a Gemini para decidir qué hacer
        """
        d = self._get_u2_device(device)
        if not d:
            return "No se pudo conectar", False
        
        self.wake_screen(device)
        self._feedback(f"🎯 {task_description[:40]}...")
        
        # Abrir app si se especificó
        if app:
            self._open_app_internal(device, app)
            time.sleep(2)
        
        # Ejecutar con el agente de visión IA
        return self._run_ai_vision_agent(device, d, task_description, message)
    
    def _run_ai_vision_agent(self, device, d, goal, message=None, max_steps=20):
        """
        AGENTE DE VISIÓN CON GEMINI
        En cada paso: VE pantalla → IA ANALIZA → IA DECIDE → EJECUTA → repite
        """
        history = []  # Historial de acciones para contexto
        consecutive_no_change = 0  # Contador de acciones sin cambio
        
        for step in range(max_steps):
            # Verificar si se solicitó detener
            if self.stop_requested:
                self.stop_requested = False
                self._feedback("⏹️ Detenido por usuario")
                return "Detenido por usuario", False
            
            # 1. VER ANTES - Capturar estado de la pantalla
            screen_before = self._capture_screen_state(d)
            
            if not screen_before['elements']:
                time.sleep(0.5)
                continue
            
            # Guardar textos para comparar después
            texts_before = set([e.get('text', '') for e in screen_before['elements'] if e.get('text')])
            
            # 2. CONSULTAR A GEMINI - Qué hacer basado en lo que ve
            action = self._ask_ai_for_action(goal, message, screen_before, history)
            
            if action is None:
                self._feedback("⚠️ Sin respuesta de IA, reintentando...")
                continue
            
            # 3. VERIFICAR si la IA dice que terminamos
            if action.get('done') or action.get('action') == 'done':
                result = action.get('result', 'Tarea completada')
                self._feedback(f"✅ {result}")
                return result, True
            
            if action.get('failed') or action.get('action') == 'failed':
                self._feedback(f"❌ {action.get('reason', 'No pude completar')}")
                return action.get('reason', 'No pude completar'), False
            
            # 4. EJECUTAR la acción
            action_type = action.get('action')
            success = self._execute_ai_action(d, action)
            
            # 5. ESPERAR y VER DESPUÉS - Verificar que algo cambió
            time.sleep(1.0)
            screen_after = self._capture_screen_state(d)
            texts_after = set([e.get('text', '') for e in screen_after['elements'] if e.get('text')])
            
            # 6. COMPARAR: ¿Cambió la pantalla?
            screen_changed = texts_before != texts_after
            new_elements = texts_after - texts_before
            
            if screen_changed:
                consecutive_no_change = 0
                if new_elements:
                    self._feedback(f"📍 Pantalla cambió")
            else:
                consecutive_no_change += 1
                self._feedback(f"⚠️ Sin cambios detectados")
                
                # Si no cambia 3 veces seguidas, hay un problema
                if consecutive_no_change >= 3:
                    self._feedback(f"❌ Acción no tiene efecto, finalizando")
                    return "No se pudo completar la acción", False
            
            # 7. VERIFICACIÓN AUTOMÁTICA: Si hicimos 'send', terminamos
            if action_type == 'send' and success:
                self._feedback(f"✅ Mensaje enviado")
                return "Mensaje enviado", True
            
            # Guardar en historial
            history.append({
                'step': step + 1,
                'action': action_type,
                'success': success,
                'changed': screen_changed,
                'target': action.get('target', '')[:20]
            })
            
            # Si ya tenemos muchos pasos, finalizar
            if len(history) >= 8:
                self._feedback(f"⚠️ Muchos pasos, finalizando")
                return "Tarea completada", True
        
        self._feedback("⚠️ Límite de pasos alcanzado")
        return "Límite de pasos", False
    
    def _capture_screen_state(self, d):
        """Captura el estado completo de la pantalla para que la IA lo analice"""
        try:
            xml = d.dump_hierarchy()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            
            elements = []
            for elem in root.iter():
                text = elem.get('text', '').strip()
                desc = elem.get('content-desc', '').strip()
                bounds = elem.get('bounds', '')
                clickable = elem.get('clickable', 'false') == 'true'
                class_name = elem.get('class', '').split('.')[-1]  # Solo el nombre corto
                
                label = text or desc
                if bounds:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        
                        # Solo incluir elementos con texto o clickeables importantes
                        if label or (clickable and class_name in ['Button', 'ImageButton', 'ImageView', 'TextView']):
                            elements.append({
                                'id': len(elements),
                                'text': label if label else f"[{class_name}]",
                                'x': cx,
                                'y': cy,
                                'clickable': clickable,
                                'type': class_name
                            })
            
            # Detectar app actual
            try:
                app_info = d.app_current()
                current_app = app_info.get('package', 'unknown').split('.')[-1]
            except:
                current_app = 'unknown'
            
            # Detectar si hay campo de texto activo
            has_input = any('EditText' in str(e.get('type', '')) for e in elements)
            
            return {
                'elements': elements[:50],  # Máximo 50 elementos
                'app': current_app,
                'has_input': has_input,
                'element_count': len(elements)
            }
        except Exception as e:
            return {'elements': [], 'app': 'unknown', 'has_input': False, 'element_count': 0}
    
    def _ask_ai_for_action(self, goal, message, screen_info, history):
        """Consulta a OpenAI qué acción tomar basado en la pantalla"""
        if not self.ai_client:
            # Sin IA, usar lógica básica
            return self._fallback_decide_action(goal, message, screen_info)
        
        # Crear descripción de la pantalla
        elements_desc = []
        for e in screen_info['elements'][:25]:
            click_str = "✓" if e['clickable'] else ""
            elements_desc.append(f"[{e['id']}] {e['text']} {click_str}")
        
        screen_text = "\n".join(elements_desc)
        
        # Historial detallado
        history_text = "ninguna"
        if history:
            history_items = [f"{h['step']}. {h['action']} → {h['target']}" for h in history[-5:]]
            history_text = "\n".join(history_items)
        
        # Detectar si probablemente ya terminamos
        task_indicators = []
        if message:
            texts_on_screen = " ".join([e.get('text', '').lower() for e in screen_info['elements']])
            if message.lower() in texts_on_screen:
                task_indicators.append(f"⚠️ El mensaje '{message}' YA ESTÁ VISIBLE")
        
        if history and any(h['action'] == 'send' for h in history):
            task_indicators.append("⚠️ Ya ejecutamos 'send' anteriormente")
        
        indicators_text = "\n".join(task_indicators) if task_indicators else ""
        
        prompt = f"""ESTADO ACTUAL:
App: {screen_info['app']}
Campo de texto: {"SÍ" if screen_info['has_input'] else "NO"}
Paso actual: {len(history) + 1}

{indicators_text}

ELEMENTOS VISIBLES:
{screen_text}

OBJETIVO: {goal}
{f"MENSAJE: {message}" if message else ""}

HISTORIAL:
{history_text}

REGLAS:
1. Si ya enviaste ('send') o el mensaje es visible → responde con "done"
2. NO sigas navegando después de completar
3. Máximo 10 pasos

Responde SOLO JSON:
{{"action": "click|type|send|done|failed", "id": N, "text": "...", "reason": "..."}}"""

        try:
            # Llamar a OpenAI
            response = self.ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en Android que analiza la pantalla y decide la mejor acción en formato JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extraer JSON de la respuesta
            action = json.loads(response_text)
                
            # Si es click, obtener coordenadas del elemento
            if action.get('action') == 'click' and 'id' in action:
                elem_id = action['id']
                for e in screen_info['elements']:
                    if e['id'] == elem_id:
                        action['x'] = e['x']
                        action['y'] = e['y']
                        action['target'] = e['text']
                        break
            
            reason = action.get('reason', '')
            if reason:
                self._feedback(f"🤔 {reason}")
            
            return action
                
        except Exception as e:
            self._feedback(f"⚠️ Error IA: {str(e)[:30]}")
        
        return self._fallback_decide_action(goal, message, screen_info)
    
    def _fallback_decide_action(self, goal, message, screen_info):
        """Lógica de fallback si Gemini no está disponible"""
        elements = screen_info.get('elements', [])
        has_input = screen_info.get('has_input', False)
        goal_lower = goal.lower()
        
        # Si hay input y mensaje, escribir y enviar
        if has_input and message:
            return {'action': 'type', 'text': message, 'reason': 'Escribiendo mensaje'}
        
        # Buscar elementos que coincidan con el objetivo
        goal_words = [w for w in goal_lower.split() if len(w) > 3]
        for elem in elements:
            if elem.get('clickable'):
                text = elem.get('text', '').lower()
                for word in goal_words:
                    if word in text:
                        return {
                            'action': 'click',
                            'x': elem['x'],
                            'y': elem['y'],
                            'target': elem['text'],
                            'reason': f"Tocando {elem['text'][:20]}"
                        }
        
        # Si piden primer chat, tocar el primer elemento clickeable en zona de chats
        if 'primer' in goal_lower and 'chat' in goal_lower:
            for elem in elements:
                if elem.get('clickable') and 200 < elem.get('y', 0) < 700:
                    return {
                        'action': 'click',
                        'x': elem['x'],
                        'y': elem['y'],
                        'target': elem['text'],
                        'reason': 'Tocando primer chat'
                    }
        
        return {'action': 'failed', 'reason': 'No sé qué hacer'}
    
    def _execute_ai_action(self, d, action):
        """Ejecuta la acción decidida por la IA"""
        action_type = action.get('action')
        
        try:
            if action_type == 'click':
                x = action.get('x')
                y = action.get('y')
                if x and y:
                    d.click(x, y)
                    target = action.get('target', '')[:20]
                    self._feedback(f"👆 {target}")
                    return True
            
            elif action_type == 'type':
                text = action.get('text', '')
                edit = d(className="android.widget.EditText")
                if edit.exists:
                    edit.set_text(text)
                    self._feedback(f"✍️ Escribí")
                    return True
            
            elif action_type == 'send':
                # Intentar botón de enviar
                send = d(descriptionContains="Enviar")
                if not send.exists:
                    send = d(descriptionContains="Send")
                if send.exists:
                    send.click()
                else:
                    d.press("enter")
                self._feedback(f"📤 Enviado")
                return True
            
            elif action_type == 'scroll':
                direction = action.get('direction', 'down')
                if direction == 'down':
                    d.swipe(0.5, 0.7, 0.5, 0.3)
                else:
                    d.swipe(0.5, 0.3, 0.5, 0.7)
                return True
            
            elif action_type == 'back':
                d.press("back")
                self._feedback(f"↩️ Atrás")
                return True
                
        except Exception as e:
            self._feedback(f"⚠️ {str(e)[:25]}")
            return False
        
        return False
    
    def _handle_popup(self, d, screen_state):
        """Detecta y cierra popups/ventanas emergentes"""
        texts = [e.get('text', '').lower() for e in screen_state.get('elements', [])]
        
        popup_buttons = ['permitir', 'allow', 'aceptar', 'accept', 'cerrar', 'close', 
                        'más tarde', 'later', 'no gracias', 'omitir', 'skip', 'ahora no']
        
        for elem in screen_state.get('elements', []):
            if elem.get('clickable'):
                label = elem.get('text', '').lower()
                if any(p in label for p in popup_buttons):
                    try:
                        d = self._get_u2_device_by_elem(elem)
                        # Priorizar "cerrar", "no", "cancelar"
                        if any(x in label for x in ['cerrar', 'close', 'no', 'cancelar', 'omitir', 'skip']):
                            return {'action': 'click', 'x': elem['x'], 'y': elem['y']}
                    except:
                        pass
        return None
    
    def _execute_whatsapp_task(self, device, d, task, message, elements):
        """Ejecuta tareas de WhatsApp de forma inteligente"""
        
        # Detectar si piden el primer chat / chat fijado
        if 'primer' in task or 'fijado' in task or 'primero' in task or 'arriba' in task:
            self._feedback(f"🔍 Buscando el primer chat de la lista...")
            
            try:
                # Método 1: Buscar la lista de chats
                # En WhatsApp, los chats están en un RecyclerView
                time.sleep(1)
                
                # Obtener el primer elemento de la lista de chats
                # Generalmente está después del header
                chat_list = d(className="android.widget.RelativeLayout", clickable=True)
                
                if chat_list.exists:
                    # Obtener el primer chat (índice 0 o 1 dependiendo del layout)
                    first_chat = chat_list[0]
                    if first_chat.exists:
                        self._feedback(f"👆 Tocando el primer chat...")
                        first_chat.click()
                        time.sleep(1.5)
                        
                        # Escribir mensaje si se proporcionó
                        if message:
                            self._feedback(f"⌨️ Escribiendo mensaje...")
                            # Buscar campo de texto
                            text_field = d(className="android.widget.EditText")
                            if text_field.exists:
                                text_field.set_text(message)
                                time.sleep(0.5)
                                
                                # Enviar
                                self._feedback(f"📤 Enviando...")
                                send_btn = d(description="Enviar")
                                if not send_btn.exists:
                                    send_btn = d(descriptionContains="Send")
                                if not send_btn.exists:
                                    # Buscar por clase típica del botón
                                    send_btn = d(resourceIdMatches=".*send.*")
                                
                                if send_btn.exists:
                                    send_btn.click()
                                    time.sleep(1)
                                    self._feedback(f"✅ Mensaje enviado al primer chat")
                                    return "Mensaje enviado al primer chat", True
                                else:
                                    # Fallback: Enter
                                    d.press("enter")
                                    self._feedback(f"✅ Mensaje enviado (via Enter)")
                                    return "Mensaje enviado al primer chat", True
                        else:
                            self._feedback(f"✅ Primer chat abierto")
                            return "Primer chat abierto", True
                
                # Método alternativo: tocar coordenadas típicas del primer chat
                self._feedback(f"🎯 Usando coordenadas del primer chat...")
                # El primer chat suele estar alrededor de y=300-400 en la mayoría de teléfonos
                d.click(0.5, 0.25)  # 50% horizontal, 25% vertical (primer chat aprox)
                time.sleep(1.5)
                
                if message:
                    self._feedback(f"⌨️ Escribiendo mensaje...")
                    text_field = d(className="android.widget.EditText")
                    if text_field.exists:
                        text_field.set_text(message)
                        time.sleep(0.5)
                        d.press("enter")
                        time.sleep(1)
                        self._feedback(f"✅ Mensaje enviado")
                        return "Mensaje enviado al primer chat", True
                
                return "Primer chat abierto (sin mensaje)", True
                
            except Exception as e:
                self._feedback(f"⚠️ Error: {e}", "warning")
                return f"Error al ejecutar tarea: {e}", False
        
        # Buscar contacto específico
        if any(word in task for word in ['busca', 'contacto', 'encuentra']):
            # Extraer nombre del contacto de la tarea
            self._feedback(f"🔍 Buscando contacto...")
            # Abrir búsqueda
            try:
                search_btn = d(description="Buscar")
                if not search_btn.exists:
                    search_btn = d(descriptionContains="Search")
                if search_btn.exists:
                    search_btn.click()
                    time.sleep(1)
            except:
                pass
            
            return "Búsqueda de contacto iniciada", True
        
        return "Tarea de WhatsApp completada", True
    
    def _execute_browser_task(self, device, d, task, elements):
        """Ejecuta tareas de navegador"""
        self._feedback(f"🌐 Ejecutando tarea de navegador...")
        return "Tarea de navegador completada", True
    
    def _execute_generic_task(self, device, d, task, elements, message=None):
        """Ejecuta tareas genéricas basándose en los elementos visibles"""
        self._feedback(f"🔧 Ejecutando tarea genérica...")
        
        # Buscar elementos que coincidan con palabras clave de la tarea
        task_words = task.lower().split()
        
        for elem in elements:
            elem_text = elem.get('text', '').lower()
            for word in task_words:
                if len(word) > 3 and word in elem_text:
                    self._feedback(f"👆 Encontrado: '{elem['text']}' - tocando...")
                    try:
                        d.click(elem['x'], elem['y'])
                        time.sleep(1)
                        return f"Tocado: {elem['text']}", True
                    except:
                        pass
        
        return "Tarea completada", True
    
    def _open_app_internal(self, device, app_name):
        """Abre una app (uso interno)"""
        app_name = app_name.lower()
        
        packages = {
            'whatsapp': 'com.whatsapp',
            'whatsapp_business': 'com.whatsapp.w4b',
            'chrome': 'com.android.chrome',
            'instagram': 'com.instagram.android',
            'facebook': 'com.facebook.katana',
            'twitter': 'com.twitter.android',
            'youtube': 'com.google.android.youtube',
            'settings': 'com.android.settings',
            'camera': 'com.android.camera',
            'messages': 'com.google.android.apps.messaging',
        }
        
        package = packages.get(app_name, app_name)
        self._run_adb(['shell', 'monkey', '-p', package, '-c', 'android.intent.category.LAUNCHER', '1'], device)
    
    def open_app(self, device, app_name):
        """Abre una aplicación"""
        self.wake_screen(device)
        self._feedback(f"📱 Abriendo {app_name}...")
        self._open_app_internal(device, app_name)
        time.sleep(2)
        return f"Abriendo {app_name}", True
    
    def go_home(self, device):
        """Va a la pantalla de inicio"""
        self.wake_screen(device)
        self._feedback("📱 Yendo a pantalla de inicio...")
        self._run_adb(['shell', 'input', 'keyevent', 'KEYCODE_HOME'], device)
        return "Pantalla de inicio", True
    
    def open_url(self, device, url):
        """Navega a una URL"""
        self.wake_screen(device)
        if not url.startswith('http'):
            url = 'https://' + url
        self._feedback(f"🌐 Navegando a {url}...")
        self._run_adb(['shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', url], device)
        time.sleep(2)
        return f"Navegando a {url}", True
    
    def click_text(self, device, text):
        """Hace clic en un elemento con cierto texto"""
        d = self._get_u2_device(device)
        if not d:
            return "No se pudo conectar", False
        
        self._feedback(f"🔍 Buscando '{text}'...")
        try:
            elem = d(textContains=text)
            if elem.exists:
                elem.click()
                self._feedback(f"✅ Clic en '{text}'")
                return f"Clic en '{text}'", True
            else:
                # Intentar por descripción
                elem = d(descriptionContains=text)
                if elem.exists:
                    elem.click()
                    return f"Clic en '{text}'", True
        except Exception as e:
            self._feedback(f"⚠️ No encontrado: {text}")
        
        return f"No se encontró '{text}'", False
    
    def scroll_and_find(self, device, text, direction='down'):
        """Hace scroll hasta encontrar un texto"""
        d = self._get_u2_device(device)
        if not d:
            return "No se pudo conectar", False
        
        self._feedback(f"🔍 Buscando '{text}' con scroll...")
        
        for i in range(5):
            elem = d(textContains=text)
            if elem.exists:
                self._feedback(f"✅ Encontrado: {text}")
                return f"Encontrado: {text}", True
            
            if direction == 'down':
                d.swipe(0.5, 0.7, 0.5, 0.3)
            else:
                d.swipe(0.5, 0.3, 0.5, 0.7)
            time.sleep(0.5)
        
        return f"No se encontró '{text}'", False
    
    def type_text(self, device, text):
        """Escribe texto"""
        d = self._get_u2_device(device)
        if d:
            self._feedback(f"⌨️ Escribiendo...")
            try:
                d.send_keys(text)
                return "Texto escrito", True
            except:
                pass
        
        # Fallback ADB
        escaped_text = text.replace(' ', '%s')
        self._run_adb(['shell', 'input', 'text', escaped_text], device)
        return "Texto escrito", True
    
    def press_button(self, device, button):
        """Presiona un botón del sistema"""
        buttons = {
            'back': 'KEYCODE_BACK',
            'home': 'KEYCODE_HOME',
            'enter': 'KEYCODE_ENTER',
            'search': 'KEYCODE_SEARCH',
        }
        keycode = buttons.get(button.lower(), 'KEYCODE_ENTER')
        self._feedback(f"🔘 Presionando {button}...")
        self._run_adb(['shell', 'input', 'keyevent', keycode], device)
        return f"Botón {button} presionado", True
    
    def take_screenshot(self, device, save_path=None):
        """Toma captura de pantalla"""
        if not save_path:
            save_path = os.path.join(os.path.expanduser('~'), 'Desktop', f'screenshot_{device[:8]}_{int(time.time())}.png')
        
        self._feedback(f"📸 Tomando captura...")
        self._run_adb(['shell', 'screencap', '-p', '/sdcard/screenshot_temp.png'], device)
        output, success = self._run_adb(['pull', '/sdcard/screenshot_temp.png', save_path], device)
        self._run_adb(['shell', 'rm', '/sdcard/screenshot_temp.png'], device)
        
        if success:
            self._feedback(f"✅ Captura guardada")
            return f"Captura guardada en {save_path}", True
        return "Error al tomar captura", False
    
    def extract_data(self, device, data_type='screen_text', app=None, navigation=None):
        """
        EXTRAE DATOS de la pantalla actual o navegando a una sección específica.
        
        data_type: 
            - 'phone_number': Busca números de teléfono en la pantalla
            - 'profile_info': Extrae información del perfil (nombre, número, estado)
            - 'screen_text': Lee todo el texto visible en la pantalla
            - 'specific': Busca texto específico
        
        app: La app donde buscar (whatsapp, whatsapp_business, instagram, etc)
        navigation: Ruta de navegación (ej: "menu>ajustes>perfil")
        """
        self.wake_screen(device)
        d = self._get_u2_device(device)
        
        if not d:
            return {"success": False, "error": "No se pudo conectar al dispositivo", "data": None}, False
        
        self._feedback(f"🔍 Extrayendo datos ({data_type})...")
        
        # Si se especifica una app, abrirla primero
        if app and app.lower() != 'any':
            self._feedback(f"📱 Abriendo {app}...")
            self._open_app_internal(device, app)
            time.sleep(2)
        
        # Si hay navegación, seguirla
        if navigation:
            self._feedback(f"🧭 Navegando: {navigation}...")
            nav_result = self._follow_navigation(device, d, navigation, app)
            if not nav_result:
                self._feedback(f"⚠️ Error en navegación, intentando leer pantalla actual...")
        
        time.sleep(1)
        
        # Extraer datos según el tipo
        extracted_data = {}
        
        try:
            # Obtener todos los elementos de texto de la pantalla
            elements = self.get_screen_elements(device)
            all_texts = [elem.get('text', '') for elem in elements if elem.get('text')]
            
            if data_type == 'phone_number':
                # Buscar patrones de números de teléfono
                phone_numbers = []
                for text in all_texts:
                    # Patrones comunes de teléfono
                    patterns = [
                        r'\+\d{1,3}\s?\d{2,4}\s?\d{4,8}',  # +54 11 12345678
                        r'\+\d{10,15}',  # +5491112345678
                        r'\d{2,4}[-\s]?\d{4}[-\s]?\d{4}',  # 11-1234-5678
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, text)
                        phone_numbers.extend(matches)
                
                # Limpiar duplicados
                phone_numbers = list(set(phone_numbers))
                extracted_data = {
                    "phone_numbers": phone_numbers,
                    "primary_number": phone_numbers[0] if phone_numbers else None
                }
                
                if phone_numbers:
                    self._feedback(f"📱 Números encontrados: {', '.join(phone_numbers)}")
                else:
                    self._feedback(f"⚠️ No se encontraron números de teléfono")
            
            elif data_type == 'profile_info':
                # Intentar extraer información de perfil
                profile_data = {
                    "name": None,
                    "phone": None,
                    "status": None,
                    "info": None
                }
                
                # Buscar número de teléfono
                for text in all_texts:
                    if re.search(r'\+\d{10,15}', text):
                        profile_data["phone"] = text
                        break
                
                # El primer texto largo suele ser el nombre
                for text in all_texts:
                    if len(text) > 2 and not re.match(r'^[\d\+\-\s]+$', text):
                        if not profile_data["name"]:
                            profile_data["name"] = text
                        elif not profile_data["status"] and len(text) > 5:
                            profile_data["status"] = text
                            break
                
                extracted_data = profile_data
                self._feedback(f"👤 Perfil: {profile_data}")
            
            elif data_type == 'screen_text':
                # Devolver todo el texto de la pantalla
                extracted_data = {
                    "all_texts": all_texts,
                    "text_count": len(all_texts),
                    "summary": " | ".join(all_texts[:10])  # Primeros 10 textos
                }
                self._feedback(f"📄 {len(all_texts)} elementos de texto encontrados")
            
            else:
                # Específico: devolver todo
                extracted_data = {
                    "elements": elements[:20],
                    "texts": all_texts
                }
            
            return {"success": True, "data": extracted_data, "error": None}, True
            
        except Exception as e:
            self._feedback(f"❌ Error extrayendo datos: {e}")
            return {"success": False, "error": str(e), "data": None}, False
    
    def _follow_navigation(self, device, d, navigation, app=None):
        """Sigue una ruta de navegación (ej: 'menu>ajustes>perfil')"""
        steps = navigation.lower().split('>')
        
        for step in steps:
            step = step.strip()
            self._feedback(f"📍 Navegando a: {step}...")
            
            try:
                if step in ['menu', '3puntos', 'mas', 'more', '⋮']:
                    # Buscar menú de 3 puntos
                    menu = d(description="Más opciones")
                    if not menu.exists:
                        menu = d(descriptionContains="More options")
                    if not menu.exists:
                        menu = d(descriptionContains="opciones")
                    if not menu.exists:
                        # Click en coordenadas típicas del menú (esquina superior derecha)
                        screen_info = d.info
                        width = screen_info.get('displayWidth', 1080)
                        d.click(width - 50, 100)
                        time.sleep(0.5)
                        continue
                    
                    if menu.exists:
                        menu.click()
                        time.sleep(0.5)
                
                elif step in ['ajustes', 'settings', 'configuracion']:
                    elem = d(textContains="Ajustes")
                    if not elem.exists:
                        elem = d(textContains="Settings")
                    if not elem.exists:
                        elem = d(textContains="Configuración")
                    
                    if elem.exists:
                        elem.click()
                        time.sleep(1)
                    else:
                        return False
                
                elif step in ['perfil', 'profile', 'cuenta']:
                    # En ajustes, el perfil suele ser el primer elemento con foto
                    # Intentar click en la parte superior donde está el perfil
                    elem = d(className="android.widget.RelativeLayout", clickable=True)
                    if elem.exists:
                        elem[0].click()
                        time.sleep(1)
                    else:
                        # Click en área del perfil (parte superior)
                        d.click(0.5, 0.15)
                        time.sleep(1)
                
                else:
                    # Buscar por texto
                    elem = d(textContains=step)
                    if elem.exists:
                        elem.click()
                        time.sleep(0.5)
                    else:
                        self._feedback(f"⚠️ No encontré: {step}")
                        return False
                
            except Exception as e:
                self._feedback(f"⚠️ Error en paso '{step}': {e}")
                return False
        
        return True
    
    def execute_and_verify(self, device, task, verification, app=None, max_retries=3):
        """
        Ejecuta una tarea Y VERIFICA que se completó.
        Si falla, REINTENTA con métodos alternativos.
        
        task: Descripción de la tarea a realizar
        verification: Qué verificar (texto esperado, elemento a buscar)
        app: Aplicación donde ejecutar
        max_retries: Número máximo de reintentos
        """
        self.wake_screen(device)
        d = self._get_u2_device(device)
        
        if not d:
            return {"success": False, "error": "No se pudo conectar", "attempts": 0}, False
        
        self._feedback(f"🎯 Iniciando tarea con verificación...")
        self._feedback(f"📋 Tarea: {task}")
        self._feedback(f"✓ Verificar: {verification}")
        
        # Métodos alternativos para intentar
        methods = [
            {"name": "método estándar", "func": lambda: self._try_standard_method(device, d, task, app)},
            {"name": "exploración UI", "func": lambda: self._try_ui_exploration(device, d, task, app)},
            {"name": "coordenadas", "func": lambda: self._try_coordinate_method(device, d, task, app)},
        ]
        
        for attempt in range(min(max_retries, len(methods))):
            method = methods[attempt]
            self._feedback(f"🔄 Intento {attempt + 1}/{max_retries}: {method['name']}...")
            
            try:
                # Ejecutar el método
                result, success = method['func']()
                
                if success:
                    time.sleep(1.5)
                    
                    # Verificar resultado
                    verified, verification_details = self._verify_task_completion(device, d, verification)
                    
                    if verified:
                        self._feedback(f"✅ Tarea COMPLETADA y VERIFICADA")
                        return {
                            "success": True, 
                            "verified": True, 
                            "attempts": attempt + 1,
                            "method": method['name'],
                            "verification_details": verification_details
                        }, True
                    else:
                        self._feedback(f"⚠️ Tarea ejecutada pero NO se pudo verificar. Reintentando...")
                
            except Exception as e:
                self._feedback(f"❌ Error en {method['name']}: {e}")
        
        # Si llegamos aquí, no pudimos completar la tarea
        self._feedback(f"❌ No se pudo completar la tarea después de {max_retries} intentos")
        return {
            "success": False, 
            "verified": False, 
            "attempts": max_retries,
            "error": "No se pudo completar la tarea con ningún método disponible"
        }, False
    
    def _try_standard_method(self, device, d, task, app):
        """Método estándar: usar explore_and_execute"""
        return self.explore_and_execute(device, task, app)
    
    def _try_ui_exploration(self, device, d, task, app):
        """Método alternativo: explorar UI con más detalle"""
        self._feedback(f"🔍 Explorando UI detalladamente...")
        
        task_lower = task.lower()
        
        # Identificar acción requerida
        if 'enviar' in task_lower or 'send' in task_lower:
            # Buscar campo de texto y botón enviar
            text_field = d(className="android.widget.EditText")
            if text_field.exists:
                # Extraer mensaje de la tarea
                msg_match = re.search(r"['\"](.+?)['\"]", task)
                if msg_match:
                    message = msg_match.group(1)
                    text_field.set_text(message)
                    time.sleep(0.5)
                    
                    # Buscar botón de enviar
                    send_variations = ["Enviar", "Send", "enviar"]
                    for send_text in send_variations:
                        send_btn = d(descriptionContains=send_text)
                        if send_btn.exists:
                            send_btn.click()
                            return "Mensaje enviado via exploración UI", True
                    
                    # Fallback: Enter
                    d.press("enter")
                    return "Mensaje enviado via Enter", True
        
        if 'abrir' in task_lower or 'tocar' in task_lower or 'click' in task_lower:
            # Extraer objetivo
            words = task_lower.split()
            for i, word in enumerate(words):
                if word in ['abrir', 'tocar', 'click'] and i + 1 < len(words):
                    target = ' '.join(words[i+1:i+3])
                    elem = d(textContains=target)
                    if elem.exists:
                        elem.click()
                        return f"Click en {target}", True
        
        return "No se pudo ejecutar con exploración UI", False
    
    def _try_coordinate_method(self, device, d, task, app):
        """Método de fallback: usar coordenadas basadas en patrones comunes"""
        self._feedback(f"📍 Usando método de coordenadas...")
        
        task_lower = task.lower()
        
        # Si es primer chat
        if 'primer' in task_lower and 'chat' in task_lower:
            # El primer chat suele estar en y=25% de la pantalla
            d.click(0.5, 0.25)
            time.sleep(1)
            
            # Escribir mensaje si hay
            msg_match = re.search(r"['\"](.+?)['\"]", task)
            if msg_match:
                message = msg_match.group(1)
                # Buscar campo de texto
                text_field = d(className="android.widget.EditText")
                if text_field.exists:
                    text_field.set_text(message)
                    time.sleep(0.5)
                    d.press("enter")
            
            return "Ejecutado via coordenadas", True
        
        return "No se pudo ejecutar con coordenadas", False
    
    def _verify_task_completion(self, device, d, verification):
        """
        Verifica que la tarea se completó correctamente.
        Retorna (verificado, detalles)
        """
        self._feedback(f"🔎 Verificando resultado...")
        
        try:
            # Obtener elementos actuales de la pantalla
            elements = self.get_screen_elements(device)
            all_texts = [elem.get('text', '').lower() for elem in elements if elem.get('text')]
            
            verification_lower = verification.lower()
            
            # Extraer texto específico a buscar
            text_to_find = None
            text_match = re.search(r"['\"](.+?)['\"]", verification)
            if text_match:
                text_to_find = text_match.group(1).lower()
            else:
                # Usar toda la verificación como texto
                text_to_find = verification_lower
            
            # Buscar en los textos
            found = False
            found_in = None
            
            for text in all_texts:
                if text_to_find in text:
                    found = True
                    found_in = text
                    break
            
            if found:
                self._feedback(f"✓ Verificación exitosa: encontré '{text_to_find}'")
                return True, {"found": True, "text": found_in}
            
            # Verificaciones adicionales
            # Buscar indicadores de éxito (check marks, ticks)
            success_indicators = ['✓', '✔', 'enviado', 'sent', 'done', 'listo', 'completado']
            for indicator in success_indicators:
                for text in all_texts:
                    if indicator in text:
                        self._feedback(f"✓ Indicador de éxito encontrado: {indicator}")
                        return True, {"found": True, "indicator": indicator}
            
            # No encontrado
            self._feedback(f"⚠️ No se encontró: '{text_to_find}'")
            return False, {"found": False, "searched_for": text_to_find, "available_texts": all_texts[:10]}
            
        except Exception as e:
            self._feedback(f"❌ Error en verificación: {e}")
            return False, {"error": str(e)}

    def send_whatsapp_complete(self, device, number_or_contact, message, app='business'):
        """Envía mensaje completo por WhatsApp"""
        self.wake_screen(device)
        
        package = 'com.whatsapp.w4b' if app == 'business' else 'com.whatsapp'
        app_name = "WhatsApp Business" if app == 'business' else "WhatsApp"
        
        number = re.sub(r'[^\d+]', '', str(number_or_contact))
        
        if not number:
            # Es un contacto, usar explore_and_execute
            return self.explore_and_execute(
                device, 
                f"Buscar el contacto {number_or_contact} y enviarle: {message}",
                app=app_name.lower().replace(' ', '_'),
                message=message
            )
        
        self._feedback(f"📱 Abriendo chat con {number}...")
        
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        url = f"https://wa.me/{number}?text={encoded_msg}"
        
        self._run_adb(['shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', url], device)
        time.sleep(4)
        
        # Enviar usando u2
        d = self._get_u2_device(device)
        if d:
            try:
                self._feedback(f"📤 Enviando mensaje...")
                send_btn = d(description="Enviar")
                if not send_btn.exists:
                    send_btn = d(descriptionContains="Send")
                if not send_btn.exists:
                    send_btn = d(resourceIdMatches=".*send.*")
                
                if send_btn.exists:
                    send_btn.click()
                    time.sleep(1)
                    self._feedback(f"✅ Mensaje enviado a {number}")
                    return f"Mensaje enviado a {number}", True
            except:
                pass
        
        # Fallback: Enter
        self._feedback(f"⌨️ Enviando con Enter...")
        self._run_adb(['shell', 'input', 'keyevent', 'KEYCODE_ENTER'], device)
        time.sleep(1)
        return f"Mensaje enviado a {number}", True


class AIAssistant:
    """Asistente de IA - AGENTE AUTÓNOMO con OpenAI"""
    
    def __init__(self, api_key=None, adb_path=None, log_callback=None):
        self.api_key = api_key
        self.log = log_callback or print
        self.client = None  # Cliente de OpenAI
        self.chat_history = []  # Historial de conversación
        self.is_configured = False
        self.device_controller = SmartDeviceController(adb_path, log_callback, None) if adb_path else None
        
        if api_key:
            self._init_model()
            # Conectar modelo al device_controller
            if self.device_controller:
                self.device_controller.ai_client = self.client
    
    def _init_model(self):
        """Inicializa el cliente de OpenAI"""
        if not OPENAI_AVAILABLE:
            self.log("OpenAI no disponible, instala: pip install openai", "error")
            return
        
        try:
            self.client = OpenAI(api_key=self.api_key)
            
            # Inicializar con el system prompt
            self.chat_history = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            
            # Test de conexión
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.chat_history + [{"role": "user", "content": "Responde solo OK"}],
                max_tokens=10
            )
            
            self.is_configured = True
            self.log("IA OpenAI configurada ✓", "success")
            
            # Conectar al device_controller
            if self.device_controller:
                self.device_controller.ai_client = self.client
                
        except Exception as e:
            self.log(f"Error al configurar OpenAI: {e}", "error")
            self.is_configured = False
    
    def configure(self, api_key, adb_path=None):
        """Configura el asistente"""
        self.api_key = api_key
        if adb_path:
            self.device_controller = SmartDeviceController(adb_path, self.log, None)
        self._init_model()
        if self.device_controller and self.client:
            self.device_controller.ai_client = self.client
    
    def update_adb_path(self, adb_path):
        """Actualiza la ruta de ADB"""
        self.device_controller = SmartDeviceController(adb_path, self.log, None)
        if self.client:
            self.device_controller.ai_client = self.client
    
    def set_feedback_callback(self, callback):
        """Configura callback para feedback"""
        if self.device_controller:
            self.device_controller.set_feedback_callback(callback)
    
    def process_message(self, user_message, devices=None):
        """Procesa mensaje del usuario con OpenAI"""
        if not self.is_configured or not self.client:
            return {
                "message": "⚠️ Configura tu API key de OpenAI.",
                "actions": [],
                "error": True
            }
        
        try:
            context = ""
            if devices:
                context = f"\n[{len(devices)} dispositivo(s)]\n"
            
            # Agregar mensaje al historial
            self.chat_history.append({
                "role": "user",
                "content": context + user_message
            })
            
            # Llamar a OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.chat_history,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Guardar respuesta en historial
            self.chat_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            # Mantener historial corto
            if len(self.chat_history) > 10:
                self.chat_history = [self.chat_history[0]] + self.chat_history[-8:]
            
            try:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                    result['error'] = False
                    return result
            except json.JSONDecodeError:
                pass
            
            return {
                "message": response_text,
                "actions": [],
                "error": False
            }
            
        except Exception as e:
            return {
                "message": f"Error: {str(e)}",
                "actions": [],
                "error": True
            }
    
    def execute_actions(self, actions, device):
        """Ejecuta acciones en un dispositivo"""
        results = []
        
        if not self.device_controller:
            return [("Sin controlador de dispositivo", False)]
        
        for action in actions:
            action_type = action.get('type', '')
            params = action.get('params', {})
            
            try:
                if action_type == 'explore_and_execute':
                    result = self.device_controller.explore_and_execute(
                        device,
                        params.get('task', ''),
                        params.get('app'),
                        params.get('message')
                    )
                elif action_type == 'send_whatsapp_complete':
                    result = self.device_controller.send_whatsapp_complete(
                        device,
                        params.get('number', ''),
                        params.get('message', ''),
                        params.get('app', 'business')
                    )
                elif action_type == 'open_app':
                    result = self.device_controller.open_app(device, params.get('app', ''))
                elif action_type == 'open_url':
                    result = self.device_controller.open_url(device, params.get('url', ''))
                elif action_type == 'click_text':
                    result = self.device_controller.click_text(device, params.get('text', ''))
                elif action_type == 'scroll_and_find':
                    result = self.device_controller.scroll_and_find(
                        device, params.get('text', ''), params.get('direction', 'down')
                    )
                elif action_type == 'type_text':
                    result = self.device_controller.type_text(device, params.get('text', ''))
                elif action_type == 'press_button':
                    result = self.device_controller.press_button(device, params.get('button', 'enter'))
                elif action_type == 'go_home':
                    result = self.device_controller.go_home(device)
                elif action_type == 'take_screenshot':
                    result = self.device_controller.take_screenshot(device)
                # Nuevas acciones de extracción y verificación
                elif action_type == 'extract_data':
                    result = self.device_controller.extract_data(
                        device,
                        params.get('data_type', 'screen_text'),
                        params.get('app'),
                        params.get('navigation')
                    )
                elif action_type == 'execute_and_verify':
                    result = self.device_controller.execute_and_verify(
                        device,
                        params.get('task', ''),
                        params.get('verification', ''),
                        params.get('app'),
                        params.get('max_retries', 3)
                    )
                # Compatibilidad
                elif action_type == 'navigate_url':
                    result = self.device_controller.open_url(device, params.get('url', ''))
                elif action_type == 'send_whatsapp':
                    result = self.device_controller.send_whatsapp_complete(
                        device, params.get('number', ''), params.get('message', ''), params.get('app', 'business')
                    )
                else:
                    result = (f"Acción desconocida: {action_type}", False)
                
                results.append(result)
                
            except Exception as e:
                results.append((f"Error: {str(e)}", False))
        
        return results
    
    def reset_chat(self):
        """Reinicia el chat de OpenAI"""
        if self.client:
            self.chat_history = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            self.log("Conversación reiniciada", "info")
            # Enviar mensaje inicial silencioso
            try:
                self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=self.chat_history + [{"role": "user", "content": "Reiniciado. Responde OK"}],
                    max_tokens=10
                )
            except:
                pass
