#!/usr/bin/env python3
import argparse
import numpy as np
import os
import sys
sys.path.append("../../../python")
import pysmurf.client
import time


def make_html(data_path):
    """
    """
    import shutil
    import fileinput
    import datetime
    import glob
    
    # FIXME - move this somewhere smarter
    template_path = '/data/smurf_data/20200304/1583352819/page_template'
    html_path = os.path.join(data_path, "summary")
    
    # Copy template directory
    shutil.copytree(template_path, html_path)

    # Load status dict
    status = np.load(os.path.join(data_path, 'outputs/status.npy')).item()
    band = status["band"]

    def replace_str(filename, search_str, replace_str):
        with fileinput.FileInput(filename, inplace=True, backup='.bak') as file:
            for line in file:
                print(line.replace(search_str, replace_str), end='')

    index_path = os.path.join(html_path, "index.html")

    # Fill why
    replace_str(index_path, "[[WHY]]",
                status['why']['output'])
    
    # Fill in time
    replace_str(index_path, "[[DATETIME]]",
                datetime.datetime.fromtimestamp(status['why']['start']).strftime('%Y-%m-%d'))

    # Do timing calculations
    skip_keys = ["band", "subband"]
    timing_str = '<table style=\"width:30%\" align=\"center\" border=\"1\">'
    timing_str += '<tr><th>Function</th><th>Time [s]</th></tr>'
    for k in list(status.keys()):
        if k not in skip_keys:
            t = status[k]['end'] - status[k]['start']
            timing_str += f'<tr><td>{k}</td><td>{t}</td></tr>'
    timing_str += '</table>'
    replace_str(index_path, "[[TIMING]]",
                timing_str)
    
    # Fill in band number
    replace_str(index_path, "[[BAND]]",
                str(band))

    # Amplifier bias
    amp_str = '<table style=\"width:30%\" align=\"center\" border=\"1\">'
    amp_dict = status['get_amplifier_bias']['output']
    for k in amp_dict.keys():
        amp_str += f'<tr><td>{k}</td><td>{amp_dict[k]}</td></tr>'
    amp_str += '</table>'
    replace_str(index_path, "[[AMPLIFIER_BIAS]]",
                amp_str)
    
    # Add full band response plot
    basename = os.path.split(status['full_band_resp']['output'][band])[1]
    basename = basename.replace('.png', '_raw.png')
    replace_str(index_path, "[[FULL_BAND_RESP]]",
                os.path.join('../plots/',basename))

    # Load tuning
    tn = np.load(status['save_tune']['output']).item()
    res = tn[band]['resonances']
    res_list = np.array([], dtype=str)
    res_name = ""
    res_to_chan = ""
    for k in list(res.keys()):
        res_list = np.append(res_list, f"{res[k]['freq']:4.3f}|{k}")
        res_name = res_name + "\'" + f"{int(k):03}|{int(k):03}" + "\', "
        chan = res[k]['channel']
        res_to_chan = res_to_chan + f'\"{int(k):03}\":\"{chan:03}\", '
        
    res_name = '[' + res_name + ']'
    replace_str(index_path, "[[FREQ_RESP_LIST]]",
                res_name)

    replace_str(index_path, "[[RES_DICT]]",
                res_to_chan)
    
    # Load eta scans
    basename = os.path.split(glob.glob(os.path.join(data_path, 'plots/*eta*'))[0])[1].split("res")
    instr = f"\'{basename[0]}\' + \'res\' + p[\'res\'] + \'.png\'"
    replace_str(index_path, "[[ETA_PATH]]",
                instr)

    # Load tracking setup
    basename = os.path.split(glob.glob(os.path.join(data_path, 'plots/*tracking*'))[0])[1].split("_band")
    instr = f"\'{basename[0]}\' + \'_band{band}_ch\' + res_to_chan(p[\'res\']) + \'.png\'"
    replace_str(index_path, "[[TRACKING_PATH]]",
                instr)
    

if __name__ == "__main__":
    #####################
    # Arg parse things
    #####################

    # Create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--epics-root", type=str, required=True,
                        help="The epics root.")
    parser.add_argument("--config-file", type=str, required=True,
                        help="The configuration file to use for this test.")
    parser.add_argument("--shelf-manager", type=str, required=True,
                        help="The shelf manager root.")
    parser.add_argument("--setup", default=False,
                        action="store_true",
                        help="Whether to run setup.")
    parser.add_argument("--band", type=int, required=True,
                        help="The band to run the analysis on.")
    parser.add_argument("--reset-rate-khz", type=int, required=False,
                        default=4,
                        help="The flux ramp reset rate")
    parser.add_argument("--n-phi0", type=float, required=False,
                        default=4,
                        help="The number of phi0 per flux ramp desired.")
    parser.add_argument("--no-find-freq", default=False,
                        action="store_true",
                        help="Skip the find_freq step")
    parser.add_argument("--no-setup-notches", default=False,
                        action="store_true",
                        help="Skip the setup_notches")
    parser.add_argument("--subband-low", type=int, required=False,
                        help="The starting subband for find_freq")
    parser.add_argument("--subband-high", type=int, required=False,
                        help="The end subband for find_freq")


    args = parser.parse_args()

    #######################
    # Actual functions
    #######################
    band = args.band
    status = {}
    status["band"] = band

    # Initialize
    S = pysmurf.client.SmurfControl(epics_root=args.epics_root,
                                    cfg_file=args.config_file,
                                    shelf_manager=args.shelf_manager,
                                    setup=False)

    print("All outputs going to: ")
    print(S.output_dir)


    def execute(status_dict, func, label, save_dict=True):
        """
        Must pass func as a lambda.
        """
        status_dict[label] = {}
        status_dict[label]['start'] = S.get_timestamp(as_int=True)
        status_dict[label]['output'] = func()
        status_dict[label]['end'] = S.get_timestamp(as_int=True)
        np.save(os.path.join(S.output_dir, "status"),
                status_dict)

        return status_dict

    # why
    status = execute(status, lambda: S.why(), 'why')

    # Setup
    if args.setup:
        status = execute(status, lambda: S.setup(), 'setup')

    # amplifier biases
    status = execute(status,
                     lambda: S.set_amplifier_bias(write_log=True),
                     'set_amplifier_bias')
    status = execute(status,
                     lambda: S.set_cryo_card_ps_en(write_log=True),
                     'amplifier_enable')
    status = execute(status,
                     lambda: S.get_amplifier_bias(),
                     'get_amplifier_bias')
    
    # full band response
    status = execute(status,
                     lambda: S.full_band_resp(2, make_plot=True,
                                              save_plot=True,
                                              show_plot=False,
                                              return_plot_path=True),
                     'full_band_resp')

    # find_freq
    if not args.no_find_freq:
        subband = np.arange(10, 120)
        if args.subband_low is not None and args.subband_high is not None:
            subband = np.arange(args.subband_low, args.subband_high)
        status['subband'] = subband
        status = execute(status,
                         lambda: S.find_freq(band, subband,
                                             make_plot=True, save_plot=True),
                         'find_freq')

    # setup notches
    if not args.no_setup_notches:
        status = execute(status,
                         lambda: S.setup_notches(band,
                                                 new_master_assignment=True),
                         'setup_notches')

        status = execute(status,
                         lambda: S.plot_tune_summary(band, eta_scan=True,
                                                     show_plot=False,
                                                     save_plot=True),
                         'plot_tune_summary')

    # Actually take a tuning serial gradient descent using tune_band_serial
    status = execute(status,
                     lambda: S.run_serial_gradient_descent(band),
                     'serial_gradient_descent')

    status = execute(status,
                     lambda: S.run_serial_eta_scan(band),
                     'serial_eta_scan')

    # track
    channel = S.which_on(band)
    status = execute(status,
                     lambda: S.tracking_setup(band, channel=channel,
                                              reset_rate_khz=args.reset_rate_khz,
                                              fraction_full_scale=.5,
                                              make_plot=True, show_plot=False,
                                              nsamp=2**18, lms_gain=8,
                                              lms_freq_hz=None,
                                              meas_lms_freq=False,
                                              meas_flux_ramp_amp=True,
                                              n_phi0=args.n_phi0,
                                              feedback_start_frac=.2,
                                              feedback_end_frac=.98),
                     'tracking_setup')
                    
    # now track and check
    status = execute(status, lambda: S.check_lock(band), 'check_lock')

    # Identify bias groups
    status = execute(status,
                     lambda: S.identify_bias_groups(bias_groups=np.arange(8),
                                                    make_plot=True, show_plot=False,
                                                    save_plot=True,
                                                    update_channel_assignment=True),
                     'identify_bias_groups')


    # Save tuning
    status = execute(status,
                     lambda: S.save_tune(),
                     'save_tune')
    

    # take data

    # read back data

    # now take data using take_noise_psd and plot stuff

    # Command and IV.


    

    # Make webpage
    make_html(os.path.split(S.output_dir)[0])
