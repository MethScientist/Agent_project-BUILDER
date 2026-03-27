# ai_models/unity_generator.py

import os
from utils.logger import log_info
from executor.file_creator import FileCreator
from executor.code_writer import CodeWriter
from context_awareness.manager import ContextManager

class UnityGenerator:
    def __init__(self, context_manager=None):
        self.creator = FileCreator()
        if context_manager is None:
            context_manager = ContextManager()
        self.writer = CodeWriter(context_manager=context_manager)
        self.base_path = "UnityGame/Assets/Scripts"
        os.makedirs(self.base_path, exist_ok=True)

    def generate_script(self, class_name: str, logic: str = ""):
        file_name = f"{class_name}.cs"
        file_path = os.path.join(self.base_path, file_name)

        script_template = f"""// Auto-generated script: {class_name}
using UnityEngine;

public class {class_name} : MonoBehaviour
{{
    void Start()
    {{
        {logic or "// Initialization logic"}
    }}

    void Update()
    {{
        {logic or "// Frame update logic"}
    }}
}}"""

        full_path = self.creator.create_file(file_path)
        self.writer.insert_code_if_missing(full_path, script_template, identifier=f"public class {class_name}")
        log_info(f"🧠 Unity script generated: {file_name}")

# ai_models/unity_generator.py (append to existing class)

    def generate_player_controller(self):
        class_name = "PlayerController"
        code = """// Controls character movement
public float speed = 5.0f;
private Rigidbody rb;

void Start()
{
    rb = GetComponent<Rigidbody>();
}

void FixedUpdate()
{
    float moveX = Input.GetAxis("Horizontal");
    float moveZ = Input.GetAxis("Vertical");
    Vector3 movement = new Vector3(moveX, 0, moveZ);
    rb.MovePosition(transform.position + movement * speed * Time.fixedDeltaTime);
}
"""
        self.generate_script(class_name, logic=code)

    def generate_camera_follow(self):
        class_name = "CameraFollow"
        code = """// Follows the player
public Transform target;
public Vector3 offset;

void LateUpdate()
{
    if (target != null)
        transform.position = target.position + offset;
}
"""
        self.generate_script(class_name, logic=code)

    def generate_game_manager(self):
        class_name = "GameManager"
        code = """// Manages game state
public static GameManager Instance;

void Awake()
{
    if (Instance == null)
    {
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }
    else
    {
        Destroy(gameObject);
    }
}"""
        self.generate_script(class_name, logic=code)
