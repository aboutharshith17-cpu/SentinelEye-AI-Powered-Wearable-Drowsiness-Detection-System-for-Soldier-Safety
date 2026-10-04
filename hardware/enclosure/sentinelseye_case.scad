[OpenSCAD]
SentinelEye Main Enclosure
Rev 1.0

module sentinelseye_case() {
  $fn=60;
  // Main body: 45mm x 35mm x 18mm rounded box
  difference() {
    minkowski() {
      cube([43, 33, 8]);
      cylinder(r=1, h=10);
    }
    // Cavity: 41mm x 31mm x 14mm
    translate([1, 1, 1])
      minkowski() {
        cube([39, 29, 12]);
        cylinder(r=0.5, h=8);
      }
  }
}

module camera_mount() {
  // Camera mount tabs
  translate([5, 5, 10])
    cube([12, 12, 2]);
  translate([5, 5, 12])
    cylinder(r=1.5, h=4);
}

module strap_holes() {
  // Watchband strap holes 20mm apart
  translate([22.5, 32, 0])
    rotate([90, 0, 0])
      cylinder(r=2.5, h=20);
}

module led_windows() {
  // Status LED windows
  translate([20, 31.5, 8])
    cylinder(r=1, h=2);
  // Alert LED window
  translate([25, 31.5, 8])
    cylinder(r=1, h=2);
}

module speaker_grille() {
  // Speaker grille holes
  for (i=[0:3])
    for (j=[0:3])
      translate([2 + i*3, 2 + j*3, 0])
        cylinder(r=0.8, h=5);
}

module faceplate_cutouts() {
  // Camera lens window
  translate([8, 8, 10])
    cylinder(r=4, h=3);
  // USB-C cutout
  translate([42, 17, 0])
    cube([3, 6, 10]);
}

// Main assembly
sentinelseye_case();
difference() {
  camera_mount();
  led_windows();
  speaker_grille();
  faceplate_cutouts();
}
strap_holes();
