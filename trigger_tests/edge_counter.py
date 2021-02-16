class edge_count:
    def __init__(self, settling_time, trig_threshold, edge_num, edge_type="rising_edge", pretrigger_ctr=1):
        self.edge_type = edge_type
        self.settling_time = settling_time
        self.trig_threshold = trig_threshold
        self.edge_num = edge_num
        self.pretrigger_ctr = pretrigger_ctr
        
    def _movavg(self, trace, win_size):
        # Basic movavg
        # https://stackoverflow.com/questions/13728392/moving-average-or-running-mean
        cumsum, moving_aves = [0], []
        for i, x in enumerate(trace):
            cumsum.append(cumsum[i-1] + x)
            if i >= win_size:
                # cummulative sum of the values within the window
                # cumsum_i: cumsum up to point i
                # cumsum_i-j: cumsum up to i, without anything before j
                moving_ave = (cumsum[i] - cumsum[i-win_size])/win_size
                moving_aves.append(moving_ave)
                
        return moving_aves
    
    def _movavg_cw(self, trace, win_size):
        cumsum_cur = 0
        moving_aves = []
        for i, x in enumerate(trace):
            cumsum_cur += trace[i]
            if i >= win_size:
                cumsum_cur = cumsum_cur - trace[i-win_size]
                moving_aves.append(cumsum_cur)
        return moving_aves
        
        
    def run(self, trace):
        trace = numpy.absolute(trace)
        # https://stackoverflow.com/questions/13728392/moving-average-or-running-mean
        averaged = self._movavg_cw(trace, self.settling_time)
        # averaged = uniform_filter1d(trace, size=self.settling_time)
        # Go through averaged trace and mark every idx
        # where the trace surpases the trigger threshold for the first time
        # but also stays above the threshold for 'pretrigger_ctr' times.
        # Reset pretrigger_ctr once the current value goes above/below threshold,
        # depending on configured edge_type.
        high = False
        triggers = []
        pretrigger_ctr = self.pretrigger_ctr
        for i, val in enumerate(averaged):
            if val > self.trig_threshold:
                if self.edge_type == "rising_edge":
                    if not high or pretrigger_ctr < self.pretrigger_ctr:
                        pretrigger_ctr -= 1
                else:
                    pretrigger_ctr = self.pretrigger_ctr
                        
                high = True
            else:
                if self.edge_type == "falling_edge":
                    if high or pretrigger_ctr < self.pretrigger_ctr:
                        pretrigger_ctr -= 1
                else:
                    pretrigger_ctr = self.pretrigger_ctr
                    
                high = False

            if pretrigger_ctr == 0:
                triggers.append(i)
                pretrigger_ctr = self.pretrigger_ctr
        
        return (averaged, triggers)