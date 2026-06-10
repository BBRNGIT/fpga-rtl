# FPGA Template Strategy: Design Once, Clone 3, Map Modules Pin-for-Pin

## Proposal Overview

Instead of designing 3 separate FPGAs (NIC, Pipeline, CPU), **design ONE generic FPGA template**, then:

1. **Clone the template 3 times** (3 instances)
2. **Assign modules to each instance** (which modules run on which FPGA)
3. **Map pins explicitly** (software assigns module I/O to FPGA pins)
4. **Validate connectivity** (all inter-FPGA wiring is explicit, routable)

This aligns with **real FPGA design methodology**:
- Define the silicon fabric once
- Map logic payloads to fabric
- Clone and re-assign for variants/products

---

## Why This Approach

### Mental Model Shift

**Old approach (modules → devices):**
```
Modules are primary
  ├─ 15 independent circuits
  ├─ Grouped into devices (NIC, Pipeline, CPU)
  └─ Devices map to FPGAs (implicit)

Result: FPGAs are containers, modules are kings
Problem: FPGA structure emerges from modules, not designed explicitly
```

**New approach (FPGA template → module assignment):**
```
FPGA is primary
  ├─ One generic template (fabric, clocks, I/O, interconnect)
  ├─ Cloned 3 times (NIC instance, Pipeline instance, CPU instance)
  ├─ Modules assigned to instances (software-driven mapping)
  └─ Pins mapped explicitly (module port ↔ FPGA pin)

Result: FPGA is the platform, modules are the payload
Benefit: Hardware-faithful, reusable, scalable
```

### Real Hardware Precedent

**Xilinx FPGA place-and-route:**
1. Define the FPGA (XCVU13P fabric, banks, clocks, I/O standards)
2. Place modules in fabric (coordinates, slices, DSPs)
3. Route signals between modules
4. Assign to pins (which module port → which physical pin)
5. Clone for multiple boards (same bitstream pattern, different pin assignments)

**Our approach mirrors this:**
1. Define FPGA template (fabric equivalent in C, clock structure, register space, interconnect)
2. Assign modules to template (which module instance goes to this FPGA)
3. Map I/O (module input/output ports → FPGA pin names/addresses)
4. Clone and validate (3 instances, different module assignments)

---

## FPGA Template Design: What It Contains

### 1. Fabric (Clock Domains & Interconnect)

```c
// fpga_template.h

#define FPGA_BASE               0x0

// Clock domain oscillators
#define FPGA_CLK_OSCILLATOR     (FPGA_BASE + 0x0000)  // free-running ref
#define FPGA_CLK_DIVIDER        (FPGA_BASE + 0x0008)  // PLL multiplier

// Clock distribution
#define FPGA_CLK_PRIMARY        (FPGA_BASE + 0x0010)  // primary clock (125 or 250 MHz)
#define FPGA_CLK_SECONDARY      (FPGA_BASE + 0x0018)  // secondary clock (if needed)

// Reset & control
#define FPGA_RESET_ACTIVE       (FPGA_BASE + 0x0020)  // global reset
#define FPGA_RESET_REASON       (FPGA_BASE + 0x0028)  // why reset happened

// Power & thermal
#define FPGA_POWER_BUDGET       (FPGA_BASE + 0x0030)  // max watts
#define FPGA_TEMP_MONITOR       (FPGA_BASE + 0x0038)  // die temp C

// Interconnect (module-to-module wiring)
#define FPGA_INTERCONNECT_BASE  (FPGA_BASE + 0x1000)  // relay bus for cross-module signals
```

### 2. Module Slots (Instance Placeholders)

```c
// fpga_template_slots.h

// Each FPGA instance has N "slots" where modules can be placed
#define FPGA_SLOT_0             (FPGA_BASE + 0x2000)  // slot 0: first module
#define FPGA_SLOT_1             (FPGA_BASE + 0x3000)  // slot 1: second module
#define FPGA_SLOT_2             (FPGA_BASE + 0x4000)  // slot 2: third module
#define FPGA_SLOT_3             (FPGA_BASE + 0x5000)  // ... up to N slots

// Each slot can hold a module descriptor
struct fpga_slot {
  char module_name[64];        // "adapter", "dom", etc.
  uint64_t module_base;        // where module's registers start
  uint64_t module_size;        // how much address space it owns
  uint64_t clock_frequency;    // primary clock for this module
  uint8_t clock_domain_id;     // which clock domain (0=mac, 1=internal, etc.)
};
```

### 3. I/O Pin Map (Module Port ↔ FPGA Pin)

```c
// fpga_pin_map.h

// FPGA has physical pins (in real hardware) or logical pin names (in simulator)
#define FPGA_PIN_COUNT          128  // total pins on this FPGA

struct fpga_pin {
  char pin_name[32];           // "J14", "M3", etc. (or "WIRE_BID_INPUT")
  char io_standard[16];        // LVCMOS18, LVDS, etc.
  uint8_t voltage_bank;        // which I/O bank (real hardware)
  
  char assigned_to[64];        // which module uses this pin
  char port_name[64];          // which module port (input/output)
};

// Software-managed pin allocation
struct fpga_pin_allocation {
  uint32_t pins_used;          // bitmap of allocated pins
  uint32_t pins_free;          // bitmap of free pins
  fpga_pin pin_map[FPGA_PIN_COUNT];
};
```

### 4. Inter-FPGA Routing (Cross-FPGA Signals)

```c
// fpga_cross_connect.h

// Some signals go FROM one FPGA TO another (e.g., NIC FPGA → Pipeline FPGA)
// Define these explicitly so place-and-route can validate them

#define FPGA_ROUTE_NIC_TO_INTERNAL_BASE  (INTERCONNECT_BASE + 0x10000)

struct fpga_route {
  char source_fpga[32];        // "NIC_FPGA"
  char dest_fpga[32];          // "PIPELINE_FPGA"
  
  char signal_name[64];        // "fifo_rx_packet"
  char source_module[64];      // "nic"
  char dest_module[64];        // "dom"
  
  uint32_t latency_cycles;     // 2 (SLR crossing + CDC)
  uint8_t cdc_required;        // 1 if crosses clock domains
};
```

---

## FPGA Instance Design: NIC, Pipeline, CPU

### Instance 1: NIC FPGA

```json
{
  "name": "NIC_FPGA",
  "template": "FPGA_TEMPLATE",
  "clock_domain_primary": "mac",
  "clock_frequency_mhz": 125,
  "clock_source": "external_phy",
  
  "modules_assigned": [
    {
      "name": "adapter",
      "slot": 0,
      "base_address": "0x1700000",
      "clock_frequency_mhz": 125,
      "clock_domain": "mac"
    },
    {
      "name": "wire",
      "slot": 1,
      "base_address": "0x1700000",
      "clock_domain": "none"
    },
    {
      "name": "mac",
      "slot": 2,
      "base_address": "0x1D00000",
      "clock_domain": "mac"
    },
    {
      "name": "tai_cdc",
      "slot": 3,
      "base_address": "0x1F00000",
      "clock_domain": "mac_to_internal_crossing"
    },
    {
      "name": "nic",
      "slot": 4,
      "base_address": "0x1A00000",
      "clock_domain": "mac"
    },
    {
      "name": "fifo_rx_writer",
      "slot": 5,
      "base_address": "0x2000000",
      "clock_domain": "mac"
    }
  ],
  
  "independent_clocks_assigned": ["taiosc", "tai"],
  
  "external_io": [
    {
      "pin_name": "ETH_RX_DATA[7:0]",
      "direction": "input",
      "module": "adapter",
      "port": "external_data_in"
    },
    {
      "pin_name": "ETH_RX_VALID",
      "direction": "input",
      "module": "adapter",
      "port": "external_valid"
    },
    {
      "pin_name": "ETH_RX_READY",
      "direction": "output",
      "module": "adapter",
      "port": "external_ready"
    }
  ],
  
  "cross_fpga_routes": [
    {
      "signal": "fifo_rx_packet",
      "destination": "PIPELINE_FPGA",
      "dest_module": "dom",
      "latency_cycles": 2,
      "cdc": "2-FF gray-code"
    }
  ]
}
```

### Instance 2: Pipeline FPGA

```json
{
  "name": "PIPELINE_FPGA",
  "template": "FPGA_TEMPLATE",
  "clock_domain_primary": "internal",
  "clock_frequency_mhz": 250,
  "clock_source": "pll_2x",
  
  "modules_assigned": [
    {
      "name": "dom",
      "slot": 0,
      "base_address": "0x2100000",
      "clock_domain": "internal"
    },
    {
      "name": "candle",
      "slot": 1,
      "base_address": "0x2200000",
      "clock_domain": "internal"
    },
    {
      "name": "footprint",
      "slot": 2,
      "base_address": "0x2300000",
      "clock_domain": "internal"
    },
    {
      "name": "tpo",
      "slot": 3,
      "base_address": "0x2400000",
      "clock_domain": "internal"
    },
    {
      "name": "timeframe",
      "slot": 4,
      "base_address": "0x1E80000",
      "clock_domain": "internal"
    },
    {
      "name": "fractal",
      "slot": 5,
      "base_address": "0x2450000",
      "clock_domain": "internal"
    },
    {
      "name": "cbr",
      "slot": 6,
      "base_address": "0x2460000",
      "clock_domain": "internal"
    },
    {
      "name": "pip_resolver",
      "slot": 7,
      "base_address": "0x2480000",
      "clock_domain": "internal"
    },
    {
      "name": "strategy",
      "slot": 8,
      "base_address": "0x2500000",
      "clock_domain": "internal"
    },
    {
      "name": "risk",
      "slot": 9,
      "base_address": "0x2600000",
      "clock_domain": "internal"
    },
    {
      "name": "oms",
      "slot": 10,
      "base_address": "0x2700000",
      "clock_domain": "internal"
    },
    {
      "name": "sor",
      "slot": 11,
      "base_address": "0x2800000",
      "clock_domain": "internal"
    },
    {
      "name": "outbound",
      "slot": 12,
      "base_address": "0x2900000",
      "clock_domain": "internal"
    },
    {
      "name": "fifo_rx_reader",
      "slot": 13,
      "base_address": "0x2000000",
      "clock_domain": "internal"
    }
  ],
  
  "external_io": [
    {
      "pin_name": "TX_DATA[7:0]",
      "direction": "output",
      "module": "outbound",
      "port": "tx_frame"
    }
  ],
  
  "cross_fpga_routes": [
    {
      "signal": "fifo_rx_packet",
      "source": "NIC_FPGA",
      "source_module": "nic",
      "latency_cycles": 2
    }
  ]
}
```

### Instance 3: CPU (Minimal, Optional)

```json
{
  "name": "CPU",
  "template": "FPGA_TEMPLATE",
  "clock_domain_primary": "cpu",
  "clock_frequency_mhz": 200,
  "clock_source": "external_host",
  
  "modules_assigned": [],  // CPU is host-side, orchestrates NIC + Pipeline
  
  "external_io": [
    {
      "pin_name": "PCIE_RX[3:0]",
      "direction": "input"
    },
    {
      "pin_name": "PCIE_TX[3:0]",
      "direction": "output"
    },
    {
      "pin_name": "UART_RX",
      "direction": "input"
    },
    {
      "pin_name": "UART_TX",
      "direction": "output"
    }
  ]
}
```

---

## Software Layer: Module Assignment & Pin Mapping

### 1. Module Assignment Tool

```python
# assign_modules_to_fpga.py

def assign_modules(template, instances, contracts):
    """Assign modules to FPGA instances based on device_assignment field."""
    
    for instance in instances:
        assigned_modules = []
        for module_name in contracts:
            contract = contracts[module_name]
            if contract["device"] == instance["name"]:
                assigned_modules.append({
                    "name": module_name,
                    "base_address": contract["address_base"],
                    "clock_domain": contract["clock_domain"]["name"],
                    "cell_count": contract["cell_count"]
                })
        
        instance["modules_assigned"] = assigned_modules
    
    return instances

# Run:
# instances = assign_modules(fpga_template, instances_json, all_contracts)
# write_instance_configs(instances)
```

### 2. Pin Allocation Tool

```python
# allocate_pins.py

def allocate_pins(instance, contracts):
    """
    For each module in this instance, allocate pins for its I/O ports.
    Validate no conflicts, all pins available.
    """
    
    pin_map = {}
    available_pins = set(instance["pin_pool"])
    
    for module_name in instance["modules_assigned"]:
        contract = contracts[module_name]
        
        for input_port in contract["inputs"]:
            # If this is an external input (not from another module on same FPGA)
            if not is_internal_source(input_port):
                pin = allocate_from_pool(available_pins, io_standard="LVCMOS18")
                pin_map[f"{module_name}.{input_port['name']}"] = pin
        
        for output_port in contract["outputs"]:
            # If this output goes external (not to another module on same FPGA)
            if output_is_external(output_port):
                pin = allocate_from_pool(available_pins, io_standard="LVCMOS18")
                pin_map[f"{module_name}.{output_port['name']}"] = pin
    
    return pin_map

# Output: pin_map.json (module.port → pin assignment)
```

### 3. Connectivity Validation

```python
# validate_connectivity.py

def validate_fpga_connectivity(instances, contracts):
    """
    Ensure all module I/O is satisfied:
    - Every module input comes from a valid source (same FPGA or cross-FPGA with CDC)
    - Every module output goes to valid destinations
    - Cross-FPGA routes are explicitly defined and CDC'd
    """
    
    for instance in instances:
        for module_name in instance["modules_assigned"]:
            contract = contracts[module_name]
            
            for input_port in contract["inputs"]:
                source = resolve_source(input_port, instance, instances, contracts)
                
                if source["fpga"] != instance["name"]:
                    # Cross-FPGA read
                    if input_port["latency_cycles"] < 2:
                        ERROR(f"{module_name}.{input_port['name']}: cross-FPGA read without CDC")
                    
                    if not has_route(instance["cross_fpga_routes"], source["module"], module_name):
                        ERROR(f"No explicit route from {source['module']} to {module_name}")
                
                else:
                    # Same-FPGA read
                    if input_port["latency_cycles"] < 1:
                        ERROR(f"{module_name}.{input_port['name']}: intra-FPGA read without register hop")
    
    return True

# validate_fpga_connectivity(instances, all_contracts)
```

---

## Workflow: Design → Clone → Assign → Validate

```
1. DESIGN FPGA TEMPLATE
   └─ Define fabric (clocks, interconnect, slots)
   └─ Define I/O pin pool (128 pins, standards)
   └─ Define cross-FPGA routes (explicit wiring schema)
   └─ Result: fpga_template.h, fpga_pin_map.h, fpga_cross_connect.h

2. CLONE FOR 3 INSTANCES
   ├─ NIC_FPGA (125 MHz MAC, 6 modules, adapts external data)
   ├─ PIPELINE_FPGA (250 MHz INTERNAL, 13 modules, processes data)
   └─ CPU (host control, admin, instrumentation)
   └─ Result: nic_fpga.json, pipeline_fpga.json, cpu.json (instance configs)

3. ASSIGN MODULES TO INSTANCES
   └─ Read contracts (all_contracts.json from contract-extractor)
   └─ For each module: which instance should it run on?
   └─ assign_modules(fpga_template, instances, contracts)
   └─ Result: instances_with_assignments.json

4. ALLOCATE PINS
   └─ For each module instance, assign I/O pins
   └─ allocate_pins(instance, contracts)
   └─ Result: pin_allocation.json (module.port → pin mapping)

5. VALIDATE CONNECTIVITY
   └─ All module inputs satisfied? ✓
   └─ All cross-FPGA reads have CDC? ✓
   └─ No pin conflicts? ✓
   └─ No address collisions? ✓
   └─ Result: validation report (pass/fail)

6. GENERATE INTEGRATION ARTIFACTS
   └─ Per-FPGA dispatch code
   └─ Pin constraints file (for place-and-route)
   └─ Wiring diagram (which module → which FPGA, which pins)
   └─ Result: nic_fpga_dispatch.c, pipeline_fpga_dispatch.c, pin_constraints.xdc
```

---

## Benefits of This Approach

### 1. Hardware-Faithful
- Real FPGA place-and-route is "template → assign logic → route pins"
- Simulator now matches hardware mental model

### 2. Reusable Template
- Design the FPGA fabric once
- Clone it 3 times with different module assignments
- Easy to create variants (e.g., "NIC FPGA v2" = template + different module assignment)

### 3. Explicit Pin Planning
- Know exactly which module uses which pins
- Prevent I/O conflicts early
- Validate before place-and-route (no surprises)

### 4. Software-Driven
- Module assignment is a data file (JSON), not hardcoded
- Tools can validate, suggest assignments, or let humans decide
- Easy to experiment with different module layouts

### 5. Scalable
- Add a new FPGA variant: clone + assign different modules
- Add a new module: assign to slot, allocate pins, validate
- 15 modules → 50 modules = same process, just more slots

### 6. CDC Enforcement
- Cross-FPGA routes explicitly defined
- Pre-commit hook: "did you CDC this cross-FPGA read?" → automatic check
- No accidental fast paths across chip boundaries

---

## Coherence with Progress So Far

**What we've built:**
- ✓ 15 graduated, valid hardware modules (payload)
- ✓ Independent clocks (5 oscillators)
- ✓ Contract schema (I/O specification)
- ✓ Device assignment (which modules → which FPGA)

**Next step (this proposal):**
- → Design FPGA template (the container)
- → Clone 3 instances (NIC, Pipeline, CPU)
- → Assign modules to instances (software-driven)
- → Validate connectivity (tools confirm wiring is correct)
- → Generate artifacts (dispatch code, pin constraints, diagrams)

**This bridges the gap** between "we have modules" and "we can synthesize this on real silicon."

---

## Recommendation

**Design the FPGA template now, before adding more modules.**

It's a 2–3 hour task:
1. Define fpga_template.h (fabric, clocks, slots, I/O)
2. Create instance configs (nic_fpga.json, pipeline_fpga.json, cpu.json)
3. Assign existing 15 modules to instances
4. Validate connectivity
5. Generate first set of integration artifacts

Result: **Explicit, hardware-faithful architecture ready for real FPGA synthesis.**
