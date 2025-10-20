%% ============================================================
%  SIRD για Μαστίτιδα με Early Detection και Υπολογισμό Κόστους
% ============================================================
clc; clear; close all;
fprintf('--- SIRD Mastitis: Baseline vs Early Detection ---\n');

% ------------------------------------------------------------
% 0) Αρχεία CSV
% ------------------------------------------------------------
files = {'farm1_metrics.csv','farm2_metrics.csv','farm4_metrics.csv','farm6_metrics.csv'};

% ------------------------------------------------------------
% 1) Ρυθμίσεις
% ------------------------------------------------------------
temp_fever_thr   = 40.0;   % °C πυρετός
lowmove_z_thr    = -1.0;   % z_acc < -1 σημαίνει χαμηλή κίνηση
recov_days_norm  = 3;
mortality_frac   = 0.03;
days_to_outcome  = 7;
days_sim         = 60;

% Οικονομικές παράμετροι
value_per_sheep       = 230;   % €
milk_loss_per_infected= 25;    % € ανά μολυσμένο/κύκλο
vet_cost              = 100;   % € ανά farm

% ------------------------------------------------------------
% 2) Φόρτωση & ένωση δεδομένων
% ------------------------------------------------------------
T = table();
for f = 1:numel(files)
    if isfile(files{f})
        Ti = readtable(files{f});
        Ti = stdcols(Ti);
        T = [T; Ti];
    end
end
assert(~isempty(T),'Δεν βρέθηκαν δεδομένα.');

col.id    = 'id_api';
col.temp  = 'mean_temp';
col.mov   = 'z_acc';
col.flag  = 'possible_sick';

% Μετατροπή possible_sick σε λογική
if iscell(T.(col.flag))
    vals = string(T.(col.flag));
    T.(col.flag) = ismember(upper(vals),["TRUE","YES","1"]);
elseif isnumeric(T.(col.flag))
    T.(col.flag) = logical(T.(col.flag));
end

% ------------------------------------------------------------
% 3) Ανίχνευση ύποπτων (baseline)
% ------------------------------------------------------------
T.fever   = T.(col.temp) >= temp_fever_thr;
T.lowmove = T.(col.mov)  <= lowmove_z_thr;
T.suspect = T.fever | T.lowmove | T.(col.flag);

animals = unique(T.(col.id));
N = numel(animals);
fprintf('Σύνολο ζώων: %d\n', N);

infected_ratio = mean(T.suspect);
I0 = round(infected_ratio*N);
S0 = N - I0; R0 = 0; D0 = 0;

% ------------------------------------------------------------
% 4) SIRD Baseline
% ------------------------------------------------------------
beta_b = 0.45; gamma_r = 0.12; gamma_d = 0.03;
[Sb,Ib,Rb,Db] = simSIRD_discrete(beta_b,gamma_r,gamma_d,N,S0,I0,R0,D0,days_sim);

% ------------------------------------------------------------
% 5) SIRD Early Detection
% ------------------------------------------------------------
beta_e = 0.25; gamma_r_e = 0.15; gamma_d_e = 0.02;
[Se,Ie,Re,De] = simSIRD_discrete(beta_e,gamma_r_e,gamma_d_e,N,S0,I0,R0,D0,days_sim);

% ------------------------------------------------------------
% 6) Οικονομική εκτίμηση
% ------------------------------------------------------------
Deaths_b = Db(end); Deaths_e = De(end);
avgI_b = mean(Ib); avgI_e = mean(Ie);

Cost_b = Deaths_b*value_per_sheep + avgI_b*milk_loss_per_infected + vet_cost;
Cost_e = Deaths_e*value_per_sheep + avgI_e*milk_loss_per_infected + vet_cost;

save_pct = 100*(1 - Cost_e/Cost_b);
fprintf('Baseline cost: €%.2f | Early Detection cost: €%.2f | Saving: %.1f%%\n', ...
        Cost_b, Cost_e, save_pct);

% ------------------------------------------------------------
% 7) Plots
% ------------------------------------------------------------
t = 1:days_sim;
figure('Position',[100 100 1200 500])

% --- SIRD καμπύλες ---
subplot(1,2,1)
hold on
plot(t,Sb,'--b','LineWidth',1.5)
plot(t,Ib,'--r','LineWidth',1.5)
plot(t,Rb,'--g','LineWidth',1.5)
plot(t,Db,'--k','LineWidth',1.5)
plot(t,Se,'b','LineWidth',2)
plot(t,Ie,'r','LineWidth',2)
plot(t,Re,'g','LineWidth',2)
plot(t,De,'k','LineWidth',2)
xlabel('Ημέρες'); ylabel('Πρόβατα');
legend({'S (Baseline)','I (Baseline)','R (Baseline)','D (Baseline)', ...
        'S (Early Det.)','I (Early Det.)','R (Early Det.)','D (Early Det.)'}, ...
        'Location','bestoutside');
grid on; title('SIRD Μαστίτιδας – Baseline vs Early Detection');
hold off

% --- Διάγραμμα κόστους ---
subplot(1,2,2)
bar([Cost_b Cost_e]); 
set(gca,'xticklabel',{'Baseline','Early Detection'});
ylabel('Συνολικό Κόστος (€)');
title(sprintf('Εξοικονόμηση: %.1f%% (%.2f €)',save_pct,Cost_b - Cost_e));
grid on; colormap([0.8 0.4 0.4; 0.3 0.8 0.3]);

sgtitle('Ανάλυση Εξέλιξης & Οικονομικής Επίδρασης Μαστίτιδας')

% ------------------------------------------------------------
% 8) Αναφορά
% ------------------------------------------------------------
fprintf('\n--- ΑΝΑΦΟΡΑ ---\n');
fprintf('Peak infected: %.1f (baseline) → %.1f (early)\n', max(Ib), max(Ie));
fprintf('Deaths: %.1f → %.1f (%.1f%% μείωση)\n', Deaths_b, Deaths_e, 100*(1-Deaths_e/Deaths_b));
fprintf('Total cost reduction: €%.2f (%.1f%%)\n', Cost_b - Cost_e, save_pct);

% ============================================================
% Συναρτήσεις
% ============================================================
function TT = stdcols(TT)
v = TT.Properties.VariableNames; 
v = regexprep(v,'\s+','_'); 
v = lower(v);
TT.Properties.VariableNames = v;
end

function [S,I,R,D] = simSIRD_discrete(beta,gamma_r,gamma_d,N,S0,I0,R0,D0,T)
S=zeros(T,1); I=zeros(T,1); R=zeros(T,1); D=zeros(T,1);
S(1)=S0; I(1)=I0; R(1)=R0; D(1)=D0;
for t=2:T
    inf_term = beta*S(t-1)*I(t-1)/N;
    rec_term = gamma_r*I(t-1);
    die_term = gamma_d*I(t-1);
    S(t)=max(0,S(t-1)-inf_term);
    I(t)=max(0,I(t-1)+inf_term-rec_term-die_term);
    R(t)=R(t-1)+rec_term;
    D(t)=D(t-1)+die_term;
end
end



