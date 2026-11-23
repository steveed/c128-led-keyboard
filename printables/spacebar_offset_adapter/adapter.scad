// Offset adapter: the C128's own (Mitsumi) spacebar on Cherry stabilizers at the standard
// MX 9u spacing.
//
// The Mitsumi bar's two stabilizer sockets are 125.35 mm apart; rev 3 drills its Cherry
// PCB-mount stabilizers 133.35 mm apart (the MX 9u spacing).  This is the
// the-c128-keyboard-project adapter (printable_parts/adapter_mitsumi_spacebar_to_cherry_
// stabilizer, by Jeff Flitton, CC-BY-SA 4.0; dimensions measured from its STL) with its MX
// socket moved `offset` mm along the bar: the plug still goes into the bar's socket, a bridge
// carries the load 4 mm outward, and the socket takes the stabilizer insert's stem there.
//
// Print two: `side = 1` for the right-hand stabilizer and `side = -1` for the left (mirror
// images: the socket always moves away from the middle of the bar).  The Makefile builds both.
//
// Coordinates as the original: z = 0 is its middle; the MX socket opens downward at
// z = -4.2, the plug points up and ends at z = 4.75.  The bar's long axis is x (`offset_axis`
// swaps it to y if a test print shows the plug's long arm should run along the bar).

side        = 1;        // 1 right stabilizer, -1 left
offset      = 4.0;      // (133.35 - 125.35) / 2
offset_axis = "x";      // "x" or "y": which way the bar runs in this part's frame
clear       = 0;        // widens the MX socket's cross slots (mm per side) if too tight

// --- the original part ----------------------------------------------------------------
body_x  = 5.1;          // block outside, x
body_y  = 6.1;          //                y
sock_z0 = -4.2;         // MX socket: open bottom ...
sock_z1 = -0.6;         //            ... to its floor (3.6 deep)
top_z   = 1.5;          // top of the block: the bar's socket post sits here
plug_z1 = 4.75;         // plug tip

// female MX cross for the stabilizer insert's stem
sock_arm_long = 4.1;    // both arms 4.1 long
sock_arm_x_w  = 1.32;   // the arm along x is 1.32 wide
sock_arm_y_w  = 1.16;   // the arm along y is 1.16 wide

// male plug into the Mitsumi bar's socket: a cross whose y arm is wider on the -y side
plug_x_len  = 4.0;      // x arm, +/-2.0
plug_x_w    = 1.46;     //        +/-0.73
plug_y_len  = 2.5;      // y arm reaches +/-2.5
plug_ym_w   = 1.46;     // -y half +/-0.73
plug_yp_w   = 0.96;     // +y half +/-0.48

eps = 0.01;

module plug() {
    translate([0, 0, top_z - eps]) linear_extrude(plug_z1 - top_z + eps) union() {
        square([plug_x_len, plug_x_w], center = true);
        translate([-plug_ym_w / 2, -plug_y_len]) square([plug_ym_w, plug_y_len]);
        translate([-plug_yp_w / 2, 0]) square([plug_yp_w, plug_y_len]);
    }
}

module socket_cross() {
    c = clear;
    translate([0, 0, sock_z0 - eps]) linear_extrude(sock_z1 - sock_z0 + eps) union() {
        square([sock_arm_long + 2 * c, sock_arm_x_w + 2 * c], center = true);
        square([sock_arm_y_w + 2 * c, sock_arm_long + 2 * c], center = true);
    }
}

module adapter() {
    d = side * offset;
    s = offset_axis == "x" ? [d, 0, 0] : [0, d, 0];
    difference() {
        union() {
            // the socket column, under the stabilizer
            translate(s) translate([-body_x / 2, -body_y / 2, sock_z0])
                cube([body_x, body_y, top_z - sock_z0]);
            // the bridge, at the old block's height: from the plug over to the column
            hull() {
                translate([-body_x / 2, -body_y / 2, sock_z1]) cube([body_x, body_y, top_z - sock_z1]);
                translate(s) translate([-body_x / 2, -body_y / 2, sock_z1])
                    cube([body_x, body_y, top_z - sock_z1]);
            }
            plug();
        }
        translate(s) socket_cross();
    }
}

adapter();
